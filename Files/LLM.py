#!/usr/bin/env python3
"""
Distributed AgroGPT inference with Qwen2.5-VL on Stampede3.
- Uses the correct Qwen2.5-VL model class
- Handles single-GPU and multi-GPU (torchrun + distributed)
- Works around home quota issues via /work caches
"""

import argparse
import json
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
import torch.distributed as dist
from PIL import Image
from torch.utils.data import DataLoader, Dataset, DistributedSampler
from transformers import AutoProcessor, Qwen2_5_VLForConditionalGeneration


DEFAULT_DATASET_BASE = Path("/work/10904/harshitha114488/LLM-test/Access")
DEFAULT_OUTPUT_DIR = Path("/work/10904/harshitha114488/LLM-test/Acess_HPC/output")
DEFAULT_INVENTORY_FILE = DEFAULT_OUTPUT_DIR / "dataset_inventory.json"
DEFAULT_MODEL_ID = "Qwen/Qwen2.5-VL-3B-Instruct"


def setup_logging(output_dir: Path, rank: int) -> logging.Logger:
    output_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("agrogpt")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] [rank=%(rank)s] %(message)s")

    class RankFilter(logging.Filter):
        def __init__(self, rank_value: int):
            super().__init__()
            self.rank_value = rank_value

        def filter(self, record):
            record.rank = self.rank_value
            return True

    rank_filter = RankFilter(rank)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.addFilter(rank_filter)
    logger.addHandler(sh)

    fh = logging.FileHandler(output_dir / f"inference_rank{rank}.log")
    fh.setFormatter(fmt)
    fh.addFilter(rank_filter)
    logger.addHandler(fh)

    return logger


class CottonImageDataset(Dataset):
    def __init__(self, inventory_path: Path, stage: Optional[str] = None):
        if not inventory_path.exists():
            raise FileNotFoundError(f"Inventory not found: {inventory_path}")

        with open(inventory_path, "r") as f:
            inventory = json.load(f)

        self.images: List[Dict[str, Any]] = []
        for classification, img_list in inventory.get("images", {}).items():
            if stage is None or classification == stage:
                self.images.extend(img_list)

    def __len__(self) -> int:
        return len(self.images)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        img_info = self.images[idx]
        return {
            "image_path": str(Path(img_info["path"])),
            "classification": img_info.get("classification", "unknown"),
            "relative_path": img_info.get("relative_path", ""),
            "size_bytes": img_info.get("size_bytes", 0),
        }


def collate_keep_list(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return batch


class AgroGPTInferencePipeline:
    def __init__(
        self,
        model_id: str,
        local_rank: int,
        world_size: int,
        logger: logging.Logger,
        max_new_tokens: int = 192,
        demo_mode: bool = False,
    ):
        self.model_id = model_id
        self.local_rank = local_rank
        self.world_size = world_size
        self.logger = logger
        self.max_new_tokens = max_new_tokens
        self.demo_mode = demo_mode

        self.device = torch.device(
            f"cuda:{local_rank}" if torch.cuda.is_available() else "cpu"
        )
        self.processor = None
        self.model = None

        self.logger.info(f"Device selected: {self.device}")

        if self.demo_mode:
            self.logger.warning("Running in DEMO mode (model loading skipped).")
            return

        self._load_model()

    def _load_model(self):
        self.logger.info(f"Loading model: {self.model_id}")
        try:
            self.processor = AutoProcessor.from_pretrained(self.model_id)

            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            self.model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
                self.model_id,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
            )

            if torch.cuda.is_available():
                torch.cuda.set_device(self.local_rank)
                self.model.to(self.device)

            self.model.eval()
            self.logger.info("Model loaded successfully.")

        except Exception as e:
            self.logger.error(f"Model load failed: {e}")
            self.logger.warning("Falling back to DEMO mode.")
            self.demo_mode = True
            self.model = None
            self.processor = None

    @staticmethod
    def generate_agro_prompt(classification: str) -> str:
        prompts = {
            "pre_defoliation": (
                "Analyze this pre-defoliation cotton UAV image and return strict JSON with keys: "
                "plant_density_per_m2, canopy_coverage_percent, leaf_color_assessment, "
                "weed_pressure, disease_or_pest_indicators."
            ),
            "post_defoliation": (
                "Analyze this post-defoliation cotton UAV image and return strict JSON with keys: "
                "boll_maturity_percent, boll_density_per_m2, defoliation_effectiveness_percent, "
                "lint_grade_indicators, harvest_readiness_score_1_to_10."
            ),
            "unknown": (
                "Analyze this cotton field image and return strict JSON with keys: "
                "growth_stage, plant_health_indicators, field_condition_assessment."
            ),
        }
        return prompts.get(classification, prompts["unknown"])

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            pass

        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass

        return {"raw_response": text, "parse_status": "not_json"}

    def _run_single_inference(self, image_path: str, classification: str) -> Dict[str, Any]:
        if self.demo_mode or self.model is None or self.processor is None:
            return {
                "status": "demonstration_mode",
                "note": "Model not loaded. Validation only.",
                "image_path_validated": os.path.exists(image_path),
            }

        if not os.path.exists(image_path):
            return {
                "status": "error",
                "error": f"Image not found: {image_path}",
            }

        prompt = self.generate_agro_prompt(classification)

        image = Image.open(image_path).convert("RGB")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        text = self.processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.processor(
            text=[text],
            images=[image],
            padding=True,
            return_tensors="pt",
        )

        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            generated_ids = self.model.generate(
                **inputs,
                max_new_tokens=self.max_new_tokens,
                do_sample=False,
            )

        generated_trimmed = [
            out_ids[in_ids.shape[0]:]
            for in_ids, out_ids in zip(inputs["input_ids"], generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_trimmed,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]

        return self._extract_json(output_text)

    def process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for item in batch:
            img_path = item["image_path"]
            classification = item.get("classification", "unknown")
            out: Dict[str, Any] = {
                "image_path": img_path,
                "classification": classification,
                "timestamp": datetime.now().isoformat(),
                "local_rank": self.local_rank,
                "inference_result": None,
                "error": None,
            }

            try:
                out["inference_result"] = self._run_single_inference(img_path, classification)
            except Exception as e:
                out["error"] = str(e)

            results.append(out)

        return results

    def run_stage(
        self,
        inventory_file: Path,
        stage: str,
        batch_size: int,
        num_workers: int,
        global_rank: int,
    ) -> List[Dict[str, Any]]:
        dataset = CottonImageDataset(inventory_file, stage=stage)
        total = len(dataset)
        if total == 0:
            self.logger.warning(f"No images found for stage: {stage}")
            return []

        sampler = None
        if self.world_size > 1:
            sampler = DistributedSampler(
                dataset,
                num_replicas=self.world_size,
                rank=global_rank,
                shuffle=False,
                drop_last=False,
            )

        loader = DataLoader(
            dataset,
            batch_size=batch_size,
            sampler=sampler,
            shuffle=False if sampler is not None else False,
            num_workers=num_workers,
            pin_memory=torch.cuda.is_available(),
            collate_fn=collate_keep_list,
        )

        all_results: List[Dict[str, Any]] = []
        processed = 0

        for i, batch in enumerate(loader):
            batch_results = self.process_batch(batch)
            all_results.extend(batch_results)
            processed += len(batch)

            if i % 10 == 0:
                self.logger.info(
                    f"Stage={stage} processed {processed}/{total} local samples"
                )

        return all_results


def init_distributed() -> Dict[str, int]:
    rank = int(os.environ.get("RANK", os.environ.get("SLURM_PROCID", 0)))
    world_size = int(os.environ.get("WORLD_SIZE", os.environ.get("SLURM_NTASKS", 1)))
    local_rank = int(os.environ.get("LOCAL_RANK", os.environ.get("SLURM_LOCALID", 0)))

    if world_size > 1 and not dist.is_initialized():
        backend = "nccl" if torch.cuda.is_available() else "gloo"
        dist.init_process_group(backend=backend, rank=rank, world_size=world_size)

    return {"rank": rank, "world_size": world_size, "local_rank": local_rank}


def gather_results(local_results: List[Dict[str, Any]], rank: int, world_size: int):
    if world_size == 1:
        return local_results

    gathered = [None for _ in range(world_size)] if rank == 0 else None
    dist.gather_object(local_results, object_gather_list=gathered, dst=0)
    if rank != 0:
        return None

    merged: List[Dict[str, Any]] = []
    for shard in gathered:
        if shard:
            merged.extend(shard)
    return merged


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="AgroGPT distributed inference")
    p.add_argument("--dataset-base", type=Path, default=DEFAULT_DATASET_BASE)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    p.add_argument("--inventory-file", type=Path, default=DEFAULT_INVENTORY_FILE)
    p.add_argument("--model-id", type=str, default=DEFAULT_MODEL_ID)
    p.add_argument("--stage", type=str, default="all", choices=["all", "pre_defoliation", "post_defoliation"])
    p.add_argument("--batch-size", type=int, default=1)
    p.add_argument("--num-workers", type=int, default=0)
    p.add_argument("--max-new-tokens", type=int, default=192)
    p.add_argument("--demo-mode", action="store_true")
    return p.parse_args()


def main():
    args = parse_args()

    dist_info = init_distributed()
    rank = dist_info["rank"]
    world_size = dist_info["world_size"]
    local_rank = dist_info["local_rank"]

    logger = setup_logging(args.output_dir, rank)
    logger.info(f"Started rank={rank} world_size={world_size} local_rank={local_rank}")

    pipeline = AgroGPTInferencePipeline(
        model_id=args.model_id,
        local_rank=local_rank,
        world_size=world_size,
        logger=logger,
        max_new_tokens=args.max_new_tokens,
        demo_mode=args.demo_mode,
    )

    stages = [args.stage] if args.stage != "all" else ["pre_defoliation", "post_defoliation"]

    output_data: Dict[str, Any] = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "rank": rank,
            "world_size": world_size,
            "model": args.model_id,
            "demo_mode": pipeline.demo_mode,
        },
        "stages": {},
    }

    for stage in stages:
        logger.info(f"=== Processing stage: {stage} ===")
        local_stage_results = pipeline.run_stage(
            inventory_file=args.inventory_file,
            stage=stage,
            batch_size=args.batch_size,
            num_workers=args.num_workers,
            global_rank=rank,
        )

        merged_stage_results = gather_results(local_stage_results, rank, world_size)
        if rank == 0:
            output_data["stages"][stage] = {
                "count": len(merged_stage_results),
                "results": merged_stage_results,
            }

        if world_size > 1:
            dist.barrier()

    if rank == 0:
        out_file = args.output_dir / f"agrogpt_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(out_file, "w") as f:
            json.dump(output_data, f, indent=2, default=str)
        logger.info(f"Saved results: {out_file}")

    if world_size > 1 and dist.is_initialized():
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
