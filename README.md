# Machine Learning Technical Report: Decision Trees & VC Dimension Theory

This repository contains the technical implementations and mathematical proofs for CS 6375 (Machine Learning) spanning algorithmic hypothesis generation (ID3 Decision Trees) and advanced generalization bounds (Vapnik-Chervonenkis Dimension Theory).

## Part 1: Algorithmic Implementation - ID3 Decision Tree

### 1.1 Overview
The objective was to build a Decision Tree classifier entirely from scratch using fundamental libraries without relying on high-level APIs like `scikit-learn`. The script parses the UCI Mushroom Dataset to differentiate poisonous vs. edible species using Information Gain as the primary heuristic.

### 1.2 Information Gain Selection
At each node, the split is chosen by maximizing the Information Gain $IG(S, A)$:
$$IG(S, A) = Entropy(S) - \sum_{v \in Values(A)} \frac{|S_v|}{|S|} Entropy(S_v)$$
Where $Entropy(S) = -p_+ \log_2 p_+ - p_- \log_2 p_-$. The dataset splits recursively, terminating when the data is entirely pure, or sub