#!/bin/bash
#SBATCH --job-name=agrogpt_inference
#SBATCH --output=/work/10904/harshitha114488/LLM-test/Acess_HPC/output/slurm_%j.log
#SBATCH --error=/work/10904/harshitha114488/LLM-test/Acess_HPC/output/slurm_%j.err
#SBATCH --time=00:40:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --partition=spr
#SBATCH --account=TG-AGR250027
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G

set -euo pipefail

PROJECT=/work/10904/harshitha114488/LLM-test
CODE=$PROJECT/Acess_HPC/Files/LLM.py
OUT=$PROJECT/Acess_HPC/output

mkdir -p "$OUT" "$PROJECT/.hf" "$PROJECT/.pyuser" "$PROJECT/.cache/pip"

export HF_HOME=$PROJECT/.hf
export HUGGINGFACE_HUB_CACHE=$HF_HOME/hub
export PYTHONUSERBASE=$PROJECT/.pyuser
export PIP_CACHE_DIR=$PROJECT/.cache/pip
export PATH=$PYTHONUSERBASE/bin:$PATH

# Use system python3 directly (no module load)
python3 -m pip install --user -U accelerate transformers safetensors pillow
srun python3 -u "$CODE" --model-id Qwen/Qwen2.5-VL-3B-Instruct --stage all --batch-size 1 --num-workers 0
