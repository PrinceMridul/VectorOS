"""The seed curriculum.

Authored content, not scraped. Four fields per node do the real pedagogical
work and are worth understanding before editing:

``canonical_model``
    The expert mental model. It is the grading key for the Metacognitive Gate
    and the leak target for :mod:`app.agents.guard`. It is **never** sent to the
    learner — write it for a marker, not for a reader.

``misconception_bank``
    Wrong models people actually hold, with lexical ``triggers``. This turns
    diagnosis into *classification against a curriculum* rather than free
    association, which is what makes the Examiner reliable enough to write to a
    learner's permanent record.

``probe_seeds``
    Socratic questions good enough to ship unassisted. When the guard rejects a
    generated coach move twice, one of these is used. The system's worst case is
    a well-written human question.

``challenge_seeds``
    Tasks ordered easiest → hardest, indexed by the ZPD selector. Every one
    demands *application*, never restatement.
"""

from __future__ import annotations

from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# 1 — How Neural Networks Learn
# ─────────────────────────────────────────────────────────────────────────────

NEURAL_NETWORKS: dict[str, Any] = {
    "slug": "how-neural-networks-learn",
    "title": "How Neural Networks Learn",
    "goal": "Understand what actually happens when a model trains.",
    "description": (
        "Not how to call fit(). What the optimiser is doing, why it sometimes fails, "
        "and how you would diagnose it at 2am."
    ),
    "estimated_hours": 5.0,
    "nodes": [
        {
            "slug": "loss-functions",
            "title": "Loss Functions",
            "one_liner": "A single number that says how wrong the model currently is.",
            "difficulty": 0.25,
            "bloom_ceiling": "analyze",
            "position": (0, 0),
            "canonical_model": (
                "A loss function maps a model's predictions and the true targets to one "
                "scalar measuring badness. Training is defined entirely by it: whatever the "
                "loss rewards is what the model becomes. Its shape over parameter space is "
                "the surface the optimiser walks, so the loss must be differentiable almost "
                "everywhere for gradient methods to work. Choice of loss encodes what kind "
                "of error you consider unacceptable — squared error punishes large mistakes "
                "disproportionately and is therefore pulled hard by outliers, while absolute "
                "error treats all misses proportionally. Cross-entropy penalises confident "
                "wrong predictions far more than uncertain ones, which is why it is used for "
                "classification. A loss is not a measure of quality in the world; it is a "
                "proxy, and the gap between the proxy and what you actually want is where "
                "most real model failures live."
            ),
            "misconception_bank": [
                {
                    "claim": "loss is the same thing as accuracy",
                    "canonical": (
                        "Accuracy counts discrete outcomes and is flat almost everywhere, so "
                        "it has no usable gradient. Loss is a continuous proxy chosen because "
                        "it can be differentiated — the two can move in opposite directions."
                    ),
                    "severity": "high",
                    "triggers": ["accuracy", "percent correct", "how accurate"],
                },
                {
                    "claim": "a lower loss always means a better model",
                    "canonical": (
                        "Lower training loss can mean memorisation. Loss is only meaningful "
                        "relative to data the model has not seen."
                    ),
                    "severity": "medium",
                    "triggers": ["lower is better", "minimise loss", "as low as possible"],
                },
                {
                    "claim": "one bad data point cannot move the model much",
                    "canonical": (
                        "Under squared error a single large error contributes quadratically, "
                        "so one mistyped value can dominate the whole loss and drag the fit "
                        "toward it. Robustness to outliers is a property of the loss you "
                        "chose, not a property models have by default."
                    ),
                    "severity": "high",
                    "triggers": [
                        "one wrong",
                        "one bad",
                        "single point",
                        "does not matter",
                        "doesn't matter",
                        "not really matter",
                        "barely affect",
                        "average out",
                    ],
                },
            ],
            "probe_seeds": [
                "If a model's loss is falling but its accuracy is not moving, what is the loss rewarding?",
                "You have one outlier that is wrong by 100. What does squared error do with it that absolute error does not?",
                "What would happen to training if we used accuracy directly as the loss?",
            ],
            "challenge_seeds": [
                "A model predicts house prices. One house in the training set was mistyped as $50,000,000. Using squared error, what happens to the fitted model — and why?",
                "You are detecting a rare disease that occurs in 1 in 1000 people. Your model reaches 99.9% accuracy by predicting 'healthy' every time. Write the loss you would use instead and justify it in terms of what the loss punishes.",
                "Two models have identical training loss. One will generalise far worse. Describe what you would measure to tell them apart, and why training loss cannot.",
            ],
            "chunks": [
                (
                    "A loss function reduces the model's entire performance on a batch to one "
                    "scalar. That reduction is the whole training signal: the optimiser has no "
                    "access to your intentions, only to this number and its slope. Whatever "
                    "behaviour reduces the loss is the behaviour you will get, including "
                    "behaviour you did not want."
                ),
                (
                    "Squared error grows quadratically with the size of a mistake, so a single "
                    "point that is wrong by 10 contributes as much as 100 points wrong by 1. "
                    "This makes it exquisitely sensitive to outliers and mislabelled data. "
                    "Absolute error grows linearly and is far more robust, at the cost of a "
                    "gradient that does not shrink as you approach the optimum."
                ),
            ],
        },
        {
            "slug": "gradients",
            "title": "Gradients & the Loss Surface",
            "one_liner": "The direction of steepest increase — and why we walk the other way.",
            "difficulty": 0.4,
            "bloom_ceiling": "analyze",
            "position": (1, 0),
            "canonical_model": (
                "The gradient is the vector of partial derivatives of the loss with respect to "
                "every parameter. It points in the direction of steepest *increase* of the "
                "loss, which is why descent moves along its negative. Its magnitude describes "
                "local steepness only — it carries no information about how far away the "
                "minimum is, which is the source of most optimisation confusion. In high "
                "dimensions the surface is not a bowl: it is dominated by saddle points and "
                "long narrow valleys rather than by local minima. A gradient near zero "
                "therefore does not mean you have arrived; it means the surface is locally "
                "flat, which happens at minima, maxima, saddles and plateaus alike."
            ),
            "misconception_bank": [
                {
                    "claim": "a large gradient means you are far from the minimum",
                    "canonical": (
                        "Magnitude measures local steepness, not distance. A cliff edge one "
                        "step from the optimum has a huge gradient; a long flat plateau miles "
                        "away has almost none."
                    ),
                    "severity": "high",
                    "triggers": ["far from", "how far", "big gradient means", "distance"],
                },
                {
                    "claim": "training gets stuck in local minima",
                    "canonical": (
                        "In high-dimensional spaces, points where every direction curves upward "
                        "are vanishingly rare. What training actually stalls on is saddle "
                        "points and plateaus."
                    ),
                    "severity": "medium",
                    "triggers": ["local minima", "local minimum", "stuck in a valley"],
                },
            ],
            "probe_seeds": [
                "The gradient is zero. Name three different situations that could produce that.",
                "If the gradient told you distance rather than steepness, what would you no longer need?",
                "Why does the negative of the gradient point downhill rather than toward the minimum?",
            ],
            "challenge_seeds": [
                "Your loss is flat for 200 steps, then suddenly drops. Explain what the surface must have looked like, in terms of gradients.",
                "A colleague says 'the gradient is tiny, so we must be nearly done'. Give a concrete situation where they are badly wrong, and say what you would check instead.",
                "You are optimising in a long narrow valley: steep across, nearly flat along. Describe what plain gradient descent does here and why it is slow, using the gradient vector directly.",
            ],
            "chunks": [
                (
                    "Each partial derivative answers one question: if I nudge this single "
                    "parameter and hold everything else fixed, how does the loss respond? "
                    "Assembling all of those answers into a vector gives the direction in "
                    "which the loss climbs fastest. Descent simply negates it."
                ),
                (
                    "Intuition trained on two-dimensional bowls misleads badly here. For a "
                    "critical point to be a local minimum in a million-dimensional space, the "
                    "surface must curve upward in a million independent directions at once. "
                    "Saddle points — up in some directions, down in others — are overwhelmingly "
                    "more common, and they stall training without trapping it."
                ),
            ],
        },
        {
            "slug": "gradient-descent",
            "title": "Gradient Descent",
            "one_liner": "Repeatedly take a small step downhill. That is the entire algorithm.",
            "difficulty": 0.5,
            "bloom_ceiling": "evaluate",
            "position": (2, 0),
            "canonical_model": (
                "Gradient descent updates parameters by subtracting the gradient scaled by a "
                "learning rate, repeatedly. It is greedy and purely local: at every step it "
                "knows only the slope where it currently stands, never the shape of the "
                "surface ahead. Stochastic gradient descent estimates that slope from a small "
                "batch instead of the full dataset, which makes each step noisy but far "
                "cheaper — and the noise itself is useful, because it lets the trajectory "
                "escape flat regions that a perfectly accurate gradient would settle into. "
                "Convergence is not guaranteed for non-convex surfaces; what practitioners "
                "rely on is that the solutions this process finds tend to generalise well, "
                "which is an empirical fact rather than a theorem."
            ),
            "misconception_bank": [
                {
                    "claim": "gradient descent finds the best possible solution",
                    "canonical": (
                        "It finds *a* point where the gradient vanishes, reachable from where "
                        "you started. On non-convex surfaces there is no guarantee of global "
                        "optimality and in practice no one checks for it."
                    ),
                    "severity": "high",
                    "triggers": ["best solution", "optimal", "global minimum", "finds the minimum"],
                },
                {
                    "claim": "the noise in SGD is purely a cost of using small batches",
                    "canonical": (
                        "The noise is also a benefit: it perturbs the trajectory out of sharp "
                        "regions and plateaus, and is part of why SGD generalises well."
                    ),
                    "severity": "medium",
                    "triggers": ["noise is bad", "noisy estimate", "less accurate"],
                },
            ],
            "probe_seeds": [
                "The algorithm only ever sees the slope where it is standing. What does that make impossible?",
                "You reduce the batch size to 1. Which part of the update changes, and which part does not?",
                "If you ran gradient descent twice from different starting points, what could differ?",
            ],
            "challenge_seeds": [
                "Two engineers train the same architecture on the same data and get different final losses. Neither made a mistake. Explain how.",
                "Full-batch gradient descent stalls on a plateau. Switching to batch size 32 escapes it within a few hundred steps. Explain the mechanism.",
                "You are asked to justify using SGD over a second-order method that uses curvature. Argue both the cost side and the generalisation side.",
            ],
            "chunks": [
                (
                    "The update rule is one line: new parameters equal old parameters minus the "
                    "learning rate times the gradient. Everything else in modern optimisation — "
                    "momentum, adaptive rates, schedules — is a modification of how that step is "
                    "sized or smoothed, not a departure from the idea."
                ),
                (
                    "A stochastic gradient is an unbiased but noisy estimate of the true "
                    "gradient. On average it points the right way; on any individual step it "
                    "may not. That jitter is what lets the trajectory shake loose from regions "
                    "where an exact gradient would come to rest."
                ),
            ],
        },
        {
            "slug": "learning-rate",
            "title": "Learning Rate & Convergence",
            "one_liner": "One number that decides whether training works at all.",
            "difficulty": 0.55,
            "bloom_ceiling": "evaluate",
            "position": (3, 0),
            "canonical_model": (
                "The learning rate scales the size of each step, not the number of steps. Too "
                "small and progress is slow but stable; too large and each step overshoots the "
                "valley floor, landing further up the opposite wall, so the loss oscillates or "
                "diverges to infinity. The usable range is bounded by the curvature of the "
                "surface: in a narrow valley the maximum stable rate is set by the steepest "
                "direction, even though the direction you actually need to travel is the "
                "shallow one, which is why plain descent is slow there. Schedules exist because "
                "the ideal rate changes during training — large early steps cover ground, small "
                "late steps settle into a basin. Divergence and stagnation look completely "
                "different in a loss curve, and telling them apart is the first diagnostic step."
            ),
            "misconception_bank": [
                {
                    "claim": "a high learning rate means the model takes more steps",
                    "canonical": (
                        "It changes the *size* of each step, not how many there are. This is the "
                        "single most common confusion about the parameter."
                    ),
                    "severity": "high",
                    "triggers": ["more steps", "number of steps", "how many steps", "faster steps"],
                },
                {
                    "claim": "if training diverges you should train for longer",
                    "canonical": (
                        "Divergence is not slow progress. More steps of an unstable process "
                        "produce a larger loss, not a smaller one."
                    ),
                    "severity": "high",
                    "triggers": ["train longer", "more epochs", "keep training"],
                },
            ],
            "probe_seeds": [
                "You are stepping down a narrow valley. What does a step that is too large land you on?",
                "The loss goes 2.1, 4.8, 19.3, NaN. Is that a rate problem or a data problem, and how would you tell?",
                "Why would the best learning rate at step 10 be wrong at step 10,000?",
            ],
            "challenge_seeds": [
                "Your loss curve oscillates between 0.9 and 3.4 and never settles. Diagnose it and say precisely what you would change.",
                "You halve the learning rate and the loss stops decreasing entirely. What does that tell you about where you were on the surface?",
                "Design a learning-rate schedule for a model that must train in 30 minutes on a noisy dataset. Justify every phase in terms of step size versus surface geometry.",
            ],
            "chunks": [
                (
                    "Picture descending a valley in fog. The gradient tells you which way is "
                    "down; the learning rate decides how long your stride is. With a stride "
                    "longer than the valley is wide, every step crosses the floor and lands "
                    "higher on the far side — and because the far wall is steeper, the next "
                    "step is longer still. That is divergence."
                ),
                (
                    "The maximum stable learning rate is governed by the steepest curvature in "
                    "the surface, but the distance you actually need to cover often lies along "
                    "the shallowest direction. This mismatch is why narrow valleys are slow, "
                    "and why momentum and adaptive methods exist."
                ),
            ],
        },
        {
            "slug": "backpropagation",
            "title": "Backpropagation",
            "one_liner": "The chain rule, applied with enough bookkeeping to be fast.",
            "difficulty": 0.7,
            "bloom_ceiling": "analyze",
            "position": (3, 1),
            "canonical_model": (
                "Backpropagation computes the gradient of the loss with respect to every "
                "parameter by applying the chain rule from the output backwards, reusing "
                "shared sub-expressions instead of recomputing them. It is not a learning "
                "algorithm — it produces gradients, and an optimiser decides what to do with "
                "them. Its efficiency comes from that reuse: computing each parameter's "
                "derivative independently would cost one forward pass per parameter, whereas "
                "backprop obtains all of them in a single backward pass. Because the chain "
                "rule multiplies terms along a path, repeated factors below one shrink "
                "gradients toward zero in early layers and repeated factors above one explode "
                "them — vanishing and exploding gradients are the same mechanism, differing "
                "only in direction."
            ),
            "misconception_bank": [
                {
                    "claim": "backpropagation is how the network learns",
                    "canonical": (
                        "Backprop computes gradients. The optimiser applies them. Swapping SGD "
                        "for Adam changes learning without changing backprop at all."
                    ),
                    "severity": "medium",
                    "triggers": ["backprop learns", "backpropagation updates", "backprop trains"],
                },
                {
                    "claim": "vanishing and exploding gradients are unrelated problems",
                    "canonical": (
                        "Both come from multiplying many terms along a path. Below one they "
                        "shrink, above one they grow — one mechanism, two directions."
                    ),
                    "severity": "medium",
                    "triggers": ["vanishing", "exploding", "different problems"],
                },
            ],
            "probe_seeds": [
                "If backprop is just the chain rule, what exactly is it saving you compared with computing each derivative directly?",
                "A 40-layer network trains fine in its last layers and not at all in its first. What is being multiplied?",
                "Which part of training would still exist if you deleted backprop and used numerical differentiation?",
            ],
            "challenge_seeds": [
                "Explain, using the chain rule, why gradients in layer 1 of a 30-layer network are systematically smaller than in layer 29.",
                "You swap every sigmoid for a ReLU and deep-layer training suddenly works. Explain what changed in the backward pass.",
                "Estimate how many forward passes naive numerical differentiation would need for a 10-million-parameter model, and use that to explain why backprop is not merely an optimisation.",
            ],
            "chunks": [
                (
                    "The backward pass walks the computation graph from the loss toward the "
                    "inputs, carrying the derivative of the loss with respect to each "
                    "intermediate value. Each node needs only its local derivative and the "
                    "value arriving from above, which is why the whole gradient costs about as "
                    "much as one forward pass."
                ),
                (
                    "Along a path through k layers, the gradient is a product of k local "
                    "derivatives. If those average 0.5, after 30 layers the factor is about "
                    "1e-9 and the early layers receive essentially no signal. If they average "
                    "1.5, the factor is about 1e5 and training explodes."
                ),
            ],
        },
        {
            "slug": "overfitting",
            "title": "Generalisation & Overfitting",
            "one_liner": "Learning the data instead of the pattern.",
            "difficulty": 0.45,
            "bloom_ceiling": "evaluate",
            "position": (1, 1),
            "canonical_model": (
                "Overfitting is when a model reduces training loss by absorbing structure that "
                "does not exist outside the training set — noise, coincidences, artefacts of "
                "collection. It is detected by the divergence between training and held-out "
                "performance, never by training loss alone. Capacity alone does not cause it: "
                "very large models can generalise well, and the relevant quantity is capacity "
                "relative to the amount and diversity of data, together with how strongly the "
                "training procedure is biased toward simple solutions. The most damaging real "
                "cases are not visible in any curve — leakage, where information about the "
                "target reaches the model through a feature it should not have, produces "
                "excellent validation numbers and a model that fails completely in production."
            ),
            "misconception_bank": [
                {
                    "claim": "overfitting means the model is too large",
                    "canonical": (
                        "Size relative to data and to the implicit bias of training is what "
                        "matters. Enormous models regularly generalise well."
                    ),
                    "severity": "medium",
                    "triggers": ["too large", "too many parameters", "too complex", "model is big"],
                },
                {
                    "claim": "if validation loss is low the model will work in production",
                    "canonical": (
                        "Only if the validation set is genuinely independent. Leakage produces "
                        "excellent validation scores and useless models."
                    ),
                    "severity": "high",
                    "triggers": ["validation", "held out", "test set", "will work"],
                },
            ],
            "probe_seeds": [
                "Training loss is 0.01 and validation loss is 0.9. Which of the two numbers told you something?",
                "What could make a validation score optimistic even with a perfectly ordinary model?",
                "If overfitting were purely about size, what would you predict about very large language models — and does that hold?",
            ],
            "challenge_seeds": [
                "A fraud model scores 0.99 AUC in validation and 0.61 in production. Give the two most likely explanations and say how you would distinguish them.",
                "You are given medical scans from two hospitals, one of which treats sicker patients. Describe the shortcut the model will learn and why standard validation misses it.",
                "Argue whether a model with more parameters than training examples must overfit, and state precisely what your answer depends on.",
            ],
            "chunks": [
                (
                    "The only evidence of generalisation is performance on data the model has "
                    "not seen and could not have seen. Everything else — training loss, "
                    "confidence, fit quality — is compatible with pure memorisation."
                ),
                (
                    "Leakage is the failure mode that survives every curve you plot. If a "
                    "feature encodes the answer (a record id correlated with outcome, a "
                    "timestamp after the event, a scanner artefact tied to a hospital), the "
                    "model will find it, validation will look superb, and production will not."
                ),
            ],
        },
        {
            "slug": "regularisation",
            "title": "Regularisation",
            "one_liner": "Deliberately making it harder to fit the training data.",
            "difficulty": 0.6,
            "bloom_ceiling": "create",
            "position": (2, 1),
            "canonical_model": (
                "Regularisation is any modification that trades training fit for expected "
                "performance on unseen data, by expressing a preference for some solutions "
                "over others. Weight decay expresses a preference for small weights; dropout "
                "prevents co-adaptation by removing units at random so no feature can rely on "
                "a fixed partner; early stopping limits how far the optimiser travels from "
                "its initialisation; data augmentation encodes invariances you know the task "
                "possesses. All of them are statements of prior belief about which solutions "
                "are plausible, and each is only correct to the extent that belief is true — "
                "augmenting with horizontal flips is regularisation for photographs of cats "
                "and corruption for photographs of text."
            ),
            "misconception_bank": [
                {
                    "claim": "regularisation makes the model better",
                    "canonical": (
                        "It makes the model *fit worse on purpose*, in exchange for better "
                        "expected performance on unseen data. If your prior is wrong, it just "
                        "makes the model worse."
                    ),
                    "severity": "medium",
                    "triggers": ["makes it better", "improves the model", "better model"],
                },
                {
                    "claim": "dropout is noise that makes training more robust generally",
                    "canonical": (
                        "Its mechanism is specific: it prevents units from co-adapting by "
                        "removing their reliable partners, forcing redundant representations."
                    ),
                    "severity": "low",
                    "triggers": ["adds noise", "random noise", "makes it robust"],
                },
            ],
            "probe_seeds": [
                "Every regulariser encodes a belief about which solutions are plausible. What does weight decay believe?",
                "When would data augmentation actively harm a model?",
                "If regularisation always helped, why is its strength a hyperparameter?",
            ],
            "challenge_seeds": [
                "You add weight decay and both training and validation loss get worse. What does that tell you about your prior?",
                "Design the augmentation set for a model reading handwritten postcodes. Justify each transformation, and name one that would be actively harmful.",
                "You have 800 labelled examples and a model that memorises them in 3 epochs. Propose a regularisation strategy, state the belief each component encodes, and describe how you would falsify each belief.",
            ],
            "chunks": [
                (
                    "Every regulariser is a prior. Weight decay says useful solutions have small "
                    "weights; early stopping says they resemble the initialisation; "
                    "augmentation says the label survives a specific transformation. The "
                    "technique helps exactly as much as the belief is true of your problem."
                ),
                (
                    "Dropout removes a random subset of units on each forward pass. A unit "
                    "cannot depend on a specific partner being present, so the network is "
                    "pushed toward redundant, distributed representations rather than fragile "
                    "co-adapted ones."
                ),
            ],
        },
    ],
    "edges": [
        ("loss-functions", "gradients"),
        ("gradients", "gradient-descent"),
        ("gradient-descent", "learning-rate"),
        ("gradients", "backpropagation"),
        ("gradient-descent", "backpropagation"),
        ("loss-functions", "overfitting"),
        ("overfitting", "regularisation"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 2 — Statistical Thinking for Decisions
# ─────────────────────────────────────────────────────────────────────────────

STATISTICS: dict[str, Any] = {
    "slug": "statistical-thinking",
    "title": "Statistical Thinking for Decisions",
    "goal": "Stop being fooled by numbers in meetings.",
    "description": (
        "The reasoning behind the tests, not the tests. Aimed at anyone who has to act on "
        "a dashboard and does not want to be wrong confidently."
    ),
    "estimated_hours": 4.0,
    "nodes": [
        {
            "slug": "variation",
            "title": "Variation & Noise",
            "one_liner": "Most differences you notice are not differences.",
            "difficulty": 0.25,
            "bloom_ceiling": "analyze",
            "position": (0, 0),
            "canonical_model": (
                "Any repeated measurement varies even when nothing has changed, and the size "
                "of that variation is a property of the process, not an error. The central "
                "question for any observed difference is therefore whether it exceeds what "
                "the process produces on its own. Reacting to ordinary variation as though it "
                "were signal — tampering — reliably makes systems worse, because the response "
                "adds a second source of variation on top of the first. Distinguishing common-"
                "cause variation, inherent to the system, from special-cause variation, which "
                "has an identifiable origin, is the entire skill."
            ),
            "misconception_bank": [
                {
                    "claim": "if a number moved, something caused it to move",
                    "canonical": (
                        "Something always causes it, but usually it is the ordinary variation "
                        "of the process rather than anything you did or can act on."
                    ),
                    "severity": "high",
                    "triggers": ["something caused", "must be a reason", "why did it change"],
                },
                {
                    "claim": "more data points always make a comparison more trustworthy",
                    "canonical": (
                        "Only against noise. More data does nothing about systematic bias — it "
                        "makes you more confident about a wrong answer."
                    ),
                    "severity": "medium",
                    "triggers": ["more data", "bigger sample", "larger sample"],
                },
            ],
            "probe_seeds": [
                "Before you ask why the number moved, what would you need to know about how much it normally moves?",
                "What would convince you this week's dip is ordinary rather than meaningful?",
                "If you responded to every fluctuation, what would happen to the amount of fluctuation?",
            ],
            "challenge_seeds": [
                "Conversion rate went from 4.1% to 3.6% this week. Your director wants to know what broke. What do you ask for before answering?",
                "A factory adjusts a machine every time output drifts from target. Output variance doubles over a month. Explain the mechanism.",
                "Design the smallest analysis that would let you tell whether a 12% drop in signups is worth investigating. State what it can and cannot rule out.",
            ],
            "chunks": [
                (
                    "Every process has a natural range. A measurement inside that range carries "
                    "no information about a change in the process, no matter how much it "
                    "differs from last week's measurement."
                ),
                (
                    "Tampering — adjusting a stable process in response to ordinary variation — "
                    "is one of the most reliable ways to make a system worse. Each correction "
                    "responds to noise and injects a new deviation."
                ),
            ],
        },
        {
            "slug": "sampling",
            "title": "Sampling & Uncertainty",
            "one_liner": "What a sample can and cannot tell you about a population.",
            "difficulty": 0.4,
            "bloom_ceiling": "analyze",
            "position": (1, 0),
            "canonical_model": (
                "A sample supports inference about a population only through the mechanism "
                "that produced it. Uncertainty from random sampling shrinks roughly with the "
                "square root of sample size, so quadrupling the sample halves the interval — "
                "but bias from *how* the sample was drawn does not shrink at all. A survey of "
                "people who answered your survey describes people who answer surveys, at any "
                "sample size. Confidence intervals quantify only the random component and are "
                "silent about the selection mechanism, which is why the sampling frame "
                "deserves more scrutiny than the arithmetic."
            ),
            "misconception_bank": [
                {
                    "claim": "a big sample means a representative sample",
                    "canonical": (
                        "Size fixes noise, not bias. A million self-selected responses describe "
                        "self-selected responders precisely."
                    ),
                    "severity": "high",
                    "triggers": ["big sample", "large enough", "millions of", "representative"],
                },
                {
                    "claim": "a 95% confidence interval means there is a 95% chance the true value is inside it",
                    "canonical": (
                        "It means the procedure produces intervals containing the true value 95% "
                        "of the time. The statement is about the method, not about this interval."
                    ),
                    "severity": "medium",
                    "triggers": ["95% chance", "probability the true", "confidence interval means"],
                },
            ],
            "probe_seeds": [
                "Who could not possibly have ended up in this sample?",
                "If you increased the sample tenfold, which of your two sources of error would improve?",
                "What is the population you actually want to describe, and how does it differ from the one you sampled?",
            ],
            "challenge_seeds": [
                "An in-app survey shows 87% satisfaction. Name the population that number actually describes.",
                "Your A/B test has 400,000 users per arm and a p-value of 0.001. Describe a realistic way it is still wrong.",
                "You must estimate average commute time for a city. Design the sampling procedure, and name the bias each design choice is defending against.",
            ],
            "chunks": [
                (
                    "Sampling error shrinks with the square root of n: to halve your interval "
                    "you need four times the data. This is the only kind of error that more "
                    "data fixes."
                ),
                (
                    "Selection bias is a property of the mechanism that decided who got "
                    "measured. It is invariant to sample size, invisible in the confidence "
                    "interval, and by far the more common cause of wrong conclusions."
                ),
            ],
        },
        {
            "slug": "base-rates",
            "title": "Base Rates",
            "one_liner": "Why a 99% accurate test for a rare thing is mostly wrong.",
            "difficulty": 0.5,
            "bloom_ceiling": "evaluate",
            "position": (2, 0),
            "canonical_model": (
                "The informativeness of evidence depends on how common the thing is before you "
                "look. With a 1-in-10,000 condition and a test with a 1% false-positive rate, "
                "roughly 100 healthy people test positive for every 1 affected person who "
                "does, so a positive result means about a 1% chance of having it. Neglecting "
                "this — substituting P(evidence | hypothesis) for P(hypothesis | evidence) — is "
                "the base-rate fallacy, and it is the mechanism behind most bad screening, "
                "most bad fraud alerting and most bad interview signals. The practical move is "
                "always to reason in counts over a concrete population rather than in "
                "percentages."
            ),
            "misconception_bank": [
                {
                    "claim": "a 99% accurate test means a positive result is 99% likely to be right",
                    "canonical": (
                        "Accuracy is P(positive | condition). What you want is P(condition | "
                        "positive), and converting between them requires the base rate."
                    ),
                    "severity": "high",
                    "triggers": ["99% accurate", "accurate test", "likely to be right", "99%"],
                },
                {
                    "claim": "rare events need more sensitive tests",
                    "canonical": (
                        "Rare events are limited by the false-positive rate, not sensitivity. "
                        "Specificity is what determines whether a positive means anything."
                    ),
                    "severity": "medium",
                    "triggers": ["more sensitive", "sensitivity", "catch more"],
                },
            ],
            "probe_seeds": [
                "Take 10,000 people. How many actually have it, and how many test positive?",
                "Which probability does 'accuracy' describe, and which one does the patient want?",
                "If you halved the false-positive rate, what happens to the meaning of a positive?",
            ],
            "challenge_seeds": [
                "A test is 99% accurate for a disease affecting 1 in 10,000. You test positive. Work out your actual risk using counts, not formulas.",
                "Your fraud model flags 2% of transactions and catches 95% of fraud. Fraud is 0.1% of volume. Describe what the review team's day looks like.",
                "A hiring signal is present in 80% of strong candidates and 10% of everyone else. Strong candidates are 5% of applicants. Evaluate whether the signal should be used, and what would change your answer.",
            ],
            "chunks": [
                (
                    "Work in counts, never percentages. Take 10,000 people, write down how many "
                    "have the condition, how many of those test positive, and how many of the "
                    "rest test positive anyway. The answer becomes obvious and stays obvious."
                ),
                (
                    "For rare conditions the false positives swamp the true positives, because "
                    "the false-positive rate applies to a vastly larger group. Improving "
                    "sensitivity barely moves the result; improving specificity moves it a lot."
                ),
            ],
        },
        {
            "slug": "correlation-causation",
            "title": "Correlation vs Causation",
            "one_liner": "The gap between 'moves together' and 'makes it move'.",
            "difficulty": 0.55,
            "bloom_ceiling": "evaluate",
            "position": (3, 0),
            "canonical_model": (
                "An association between two variables is compatible with several structures: A "
                "causes B, B causes A, a common cause drives both, or the sample was selected "
                "in a way that manufactures the link. Distinguishing them requires either "
                "intervention — changing A and observing B — or an argument about the causal "
                "structure that the data alone cannot supply. Controlling for more variables "
                "is not automatically safer: conditioning on a common *effect* of two "
                "independent causes creates a spurious association between them, so a control "
                "can introduce the bias it was meant to remove. Which variables to adjust for "
                "is a question about mechanism, not about the dataset."
            ),
            "misconception_bank": [
                {
                    "claim": "controlling for more variables makes an analysis more reliable",
                    "canonical": (
                        "Conditioning on a collider — a common effect — creates associations "
                        "that are not there. Which controls are valid depends on the causal "
                        "structure, not on how many are available."
                    ),
                    "severity": "high",
                    "triggers": ["control for", "adjust for", "more variables", "hold constant"],
                },
                {
                    "claim": "correlation suggests causation even if it does not prove it",
                    "canonical": (
                        "It constrains the set of possible structures without favouring any of "
                        "them. Confounding and selection can produce arbitrarily strong "
                        "correlations with no causal path at all."
                    ),
                    "severity": "medium",
                    "triggers": ["suggests", "implies", "probably causes", "evidence of causation"],
                },
            ],
            "probe_seeds": [
                "Name a third variable that could produce this association without either causing the other.",
                "What intervention would separate these explanations, even in principle?",
                "Could the way this sample was collected have created the correlation by itself?",
            ],
            "challenge_seeds": [
                "Users of your mobile app retain better than web users. Give three structures that explain this, only one of which justifies investing in mobile.",
                "Among hospitalised patients, smoking appears protective against a disease. Explain how selection produced this.",
                "You cannot run an experiment. Design the strongest observational argument you can for a causal claim, and state exactly what it still cannot rule out.",
            ],
            "chunks": [
                (
                    "Four structures produce the same correlation: A→B, B→A, C→both, and "
                    "selection on a common effect. The data cannot distinguish them. Only "
                    "intervention or an argument about mechanism can."
                ),
                (
                    "Colliders are the counter-intuitive case. If two independent causes both "
                    "affect whether a record enters your dataset, then within that dataset they "
                    "will appear related — and 'controlling for' the collider makes it worse."
                ),
            ],
        },
        {
            "slug": "significance",
            "title": "What p-values Actually Say",
            "one_liner": "A statement about data under an assumption — nothing more.",
            "difficulty": 0.65,
            "bloom_ceiling": "evaluate",
            "position": (4, 0),
            "canonical_model": (
                "A p-value is the probability of observing data at least as extreme as yours, "
                "assuming the null hypothesis is true. It is not the probability the null is "
                "true, not the probability your result is a fluke, and not a measure of effect "
                "size. A small p-value with a trivial effect is common in large samples and "
                "usually irrelevant to a decision; a large p-value with a wide interval means "
                "the study was uninformative, not that the effect is absent. Because the "
                "threshold is arbitrary and the analysis has many degrees of freedom, "
                "significance is easy to manufacture by testing multiple outcomes, stopping "
                "when the number looks right, or choosing the subgroup afterwards."
            ),
            "misconception_bank": [
                {
                    "claim": "p < 0.05 means there is a 95% chance the effect is real",
                    "canonical": (
                        "It is P(data this extreme | no effect), not P(effect | data). Getting "
                        "to the latter requires a prior."
                    ),
                    "severity": "high",
                    "triggers": ["95% chance", "probability it is real", "chance the effect"],
                },
                {
                    "claim": "a non-significant result means there is no effect",
                    "canonical": (
                        "It means the study could not distinguish the effect from zero. Absence "
                        "of evidence, with an interval wide enough to contain effects you care "
                        "about."
                    ),
                    "severity": "high",
                    "triggers": ["no effect", "not significant", "no difference", "nothing there"],
                },
            ],
            "probe_seeds": [
                "The p-value assumes something is true in order to be computed. What?",
                "You ran 20 comparisons and one came back at p = 0.04. What do you expect by chance?",
                "The effect is significant and its size is 0.2%. What decision does that support?",
            ],
            "challenge_seeds": [
                "An A/B test gives p = 0.03 and a 0.1% lift on a metric worth $2M a year. Decide whether to ship, and say what the p-value contributed to your decision.",
                "A team checks their test every morning and stops when it reaches significance. Explain what that does to their false-positive rate.",
                "Rewrite this conclusion honestly: 'the treatment had no effect (p = 0.21)'. State what would be needed to support the original claim.",
            ],
            "chunks": [
                (
                    "The definition is doing all the work: probability of data this extreme, "
                    "given the null. Every common misinterpretation comes from swapping the "
                    "two sides of that conditional."
                ),
                (
                    "Optional stopping — peeking and stopping when significant — inflates the "
                    "false-positive rate far above the nominal threshold, because with enough "
                    "looks a random walk will cross the line eventually."
                ),
            ],
        },
    ],
    "edges": [
        ("variation", "sampling"),
        ("sampling", "base-rates"),
        ("sampling", "correlation-causation"),
        ("base-rates", "significance"),
        ("correlation-causation", "significance"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# 3 — Distributed Systems Intuition
# ─────────────────────────────────────────────────────────────────────────────

DISTRIBUTED: dict[str, Any] = {
    "slug": "distributed-systems-intuition",
    "title": "Distributed Systems Intuition",
    "goal": "Reason about systems where things fail independently.",
    "description": (
        "The mental models behind the war stories: partial failure, consistency, retries, "
        "and why the network is never as reliable as your diagram."
    ),
    "estimated_hours": 4.5,
    "nodes": [
        {
            "slug": "latency",
            "title": "Latency & Physical Limits",
            "one_liner": "Some numbers are set by physics, not by your code.",
            "difficulty": 0.3,
            "bloom_ceiling": "analyze",
            "position": (0, 0),
            "canonical_model": (
                "Latency has a floor set by distance and the speed of signal propagation: "
                "roughly 30ms round trip across the Atlantic, and no amount of optimisation "
                "moves it. Bandwidth and latency are independent — a fat pipe does not make a "
                "round trip shorter — so a chatty protocol is slow on a fast link. Because "
                "latencies compose, a request that makes ten sequential calls inherits ten "
                "round trips, which is why the shape of a call graph matters more than the "
                "speed of any component. Tail latency, not average, determines user "
                "experience: if a page needs 20 backend calls each with a 1% chance of being "
                "slow, most page loads hit at least one slow call."
            ),
            "misconception_bank": [
                {
                    "claim": "a faster network connection reduces latency",
                    "canonical": (
                        "Bandwidth and latency are different quantities. More bandwidth moves "
                        "more bytes per second; it does not shorten the round trip."
                    ),
                    "severity": "medium",
                    "triggers": [
                        "faster connection",
                        "more bandwidth",
                        "faster internet",
                        "gigabit",
                    ],
                },
                {
                    "claim": "average latency is what users experience",
                    "canonical": (
                        "Users experience the tail. Fan out to enough services and nearly every "
                        "request contains at least one slow call."
                    ),
                    "severity": "high",
                    "triggers": ["average latency", "mean response", "p50", "typically"],
                },
            ],
            "probe_seeds": [
                "Which part of the delay would survive an infinitely fast network?",
                "Your service is at p50 = 5ms and p99 = 900ms. Which one does a page with 30 calls feel?",
                "What happens to total latency if you turn one call into ten sequential ones?",
            ],
            "challenge_seeds": [
                "Your API is 10ms in your datacentre and 400ms for users in Sydney. Say what you can and cannot fix.",
                "A page makes 20 parallel backend calls, each with p99 = 500ms. Estimate the fraction of page loads that take over 500ms, and explain the arithmetic.",
                "Design the call structure for a checkout page under a 200ms budget with services 30ms apart. Justify every sequential dependency you keep.",
            ],
            "chunks": [
                (
                    "Light in fibre covers roughly 200,000 km per second. London to New York and "
                    "back is about 11,000 km, so ~55ms is the floor before any processing. No "
                    "amount of engineering removes it; only moving the data closer does."
                ),
                (
                    "With 20 independent calls each having a 1% chance of exceeding 500ms, the "
                    "probability that at least one does is 1 − 0.99²⁰ ≈ 18%. Fan-out converts "
                    "rare slowness into common slowness."
                ),
            ],
        },
        {
            "slug": "partial-failure",
            "title": "Partial Failure",
            "one_liner": "The defining problem: some of it worked.",
            "difficulty": 0.45,
            "bloom_ceiling": "evaluate",
            "position": (1, 0),
            "canonical_model": (
                "In a single process, a call either returns or the whole process dies. Across a "
                "network a third outcome exists: you do not find out. A timeout tells you "
                "nothing about whether the other side executed the request — the message may "
                "have been lost outbound, the work may have completed with the reply lost, or "
                "it may still be running. This ambiguity, not the failure rate, is what makes "
                "distributed systems hard, and it is why every remote mutation needs a story "
                "for 'it might have happened'. A slow node is worse than a dead one, because "
                "dead nodes are detectable and slow nodes silently consume the callers' "
                "resources."
            ),
            "misconception_bank": [
                {
                    "claim": "a timeout means the request failed",
                    "canonical": (
                        "A timeout means you did not hear back. The operation may have "
                        "completed, may be running now, or may never have arrived."
                    ),
                    "severity": "high",
                    "triggers": ["timeout means", "request failed", "it failed", "didn't work"],
                },
                {
                    "claim": "adding retries makes a system more reliable",
                    "canonical": (
                        "Retries duplicate work under ambiguity and add load exactly when the "
                        "system is struggling. Without idempotency and backoff they turn a "
                        "brownout into an outage."
                    ),
                    "severity": "high",
                    "triggers": ["just retry", "add retries", "retry it", "try again"],
                },
            ],
            "probe_seeds": [
                "Your payment call timed out. List the states the remote system could be in right now.",
                "Which is easier to handle: a node that is down, or a node answering in 30 seconds?",
                "If every client retries the moment a service slows, what does the service see?",
            ],
            "challenge_seeds": [
                "A charge card call times out. Describe what you do next and what could go wrong with each option.",
                "One database replica is responding in 40 seconds instead of failing. Explain how that takes down services that do not depend on it.",
                "Design the failure handling for an order service that calls inventory, payment and email. State what happens if each times out, and which are safe to retry.",
            ],
            "chunks": [
                (
                    "The three outcomes of a remote call are success, failure, and unknown. "
                    "Local programming has no equivalent of the third, which is why intuition "
                    "transfers so badly."
                ),
                (
                    "A slow dependency propagates backwards: callers hold connections and "
                    "threads waiting, exhaust their pools, and become slow to *their* callers. "
                    "This is how one degraded service takes out a system that was supposedly "
                    "isolated from it."
                ),
            ],
        },
        {
            "slug": "idempotency",
            "title": "Idempotency & Retries",
            "one_liner": "Make 'do it again' safe, then retrying is safe.",
            "difficulty": 0.5,
            "bloom_ceiling": "create",
            "position": (2, 0),
            "canonical_model": (
                "An operation is idempotent when applying it more than once has the same effect "
                "as applying it once. Because a caller can never know whether an ambiguous "
                "request took effect, idempotency is what converts an unanswerable question "
                "into a safe action. It is usually achieved with a client-supplied key that the "
                "server records atomically with the effect, so a repeat is recognised and the "
                "original result returned. Note that natural idempotency of the *verb* is not "
                "enough — setting a field to a value is idempotent, incrementing it is not, and "
                "'create if absent' is only idempotent if the absence check and the create "
                "happen in one atomic step. Retries also need backoff and jitter, or "
                "synchronised clients will retry in unison and produce a thundering herd."
            ),
            "misconception_bank": [
                {
                    "claim": "GET requests are idempotent so retries are always safe",
                    "canonical": (
                        "Safety of retry is about the effect on state, not the verb. A GET that "
                        "triggers expensive work is not free to repeat, and a POST with an "
                        "idempotency key is safe to repeat."
                    ),
                    "severity": "medium",
                    "triggers": ["get requests", "read only", "safe verb", "http method"],
                },
                {
                    "claim": "checking whether the record exists before inserting makes it idempotent",
                    "canonical": (
                        "Check-then-act is a race. Two concurrent retries both check, both find "
                        "nothing, and both insert. It must be one atomic operation."
                    ),
                    "severity": "high",
                    "triggers": ["check if exists", "if not exists", "check first", "look it up"],
                },
            ],
            "probe_seeds": [
                "Two copies of the same request arrive at the same millisecond. Walk me through your check-then-insert.",
                "Which of these is idempotent: set balance to 100, or add 100 to balance?",
                "If every client retried after exactly one second, what would the server see?",
            ],
            "challenge_seeds": [
                "Design an idempotent 'charge this card' endpoint. Say what the key is, who generates it, and where it is stored relative to the charge.",
                "Your retry storm takes down a recovering service. Describe the backoff policy you would deploy and what jitter is defending against.",
                "A workflow sends an email, writes a record and calls a partner API. Make the whole thing safe to retry, and state which step forced your design.",
            ],
            "chunks": [
                (
                    "The standard construction: the client generates a unique key per logical "
                    "operation and sends it with every retry. The server stores the key together "
                    "with the effect in a single atomic write, so a duplicate is detected and "
                    "the original response replayed."
                ),
                (
                    "Exponential backoff spreads retries over time; jitter spreads them across "
                    "clients. Without jitter, clients that failed together retry together, and "
                    "the recovering service is hit by the same spike that felled it."
                ),
            ],
        },
        {
            "slug": "consistency",
            "title": "Consistency Models",
            "one_liner": "What 'the data is correct' is allowed to mean.",
            "difficulty": 0.65,
            "bloom_ceiling": "evaluate",
            "position": (3, 0),
            "canonical_model": (
                "A consistency model is a contract about which orderings of operations a system "
                "may expose to readers. Strong consistency makes replicated data behave like a "
                "single copy, at the cost of coordination on every operation — which means "
                "latency, and unavailability when the coordination cannot complete. Eventual "
                "consistency permits replicas to disagree temporarily and converge later, "
                "buying availability and speed at the cost of readers seeing stale or "
                "out-of-order state. The important intermediate guarantees are usually about "
                "one client's own view: read-your-writes and monotonic reads eliminate most "
                "user-visible weirdness without global coordination. During a network "
                "partition a system must choose between refusing writes and accepting "
                "divergence — that is a product decision about which failure the user should "
                "experience, not a technical one."
            ),
            "misconception_bank": [
                {
                    "claim": "eventual consistency means the data is sometimes wrong",
                    "canonical": (
                        "It means readers may observe an older correct state. The system "
                        "converges; it does not corrupt."
                    ),
                    "severity": "medium",
                    "triggers": ["wrong data", "incorrect", "data is bad", "loses data"],
                },
                {
                    "claim": "you pick two of consistency, availability and partition tolerance",
                    "canonical": (
                        "Partitions are not optional — networks fail whether you choose them or "
                        "not. The real choice is what to do *during* a partition, and how to "
                        "trade latency against consistency the rest of the time."
                    ),
                    "severity": "high",
                    "triggers": ["cap theorem", "pick two", "choose two", "cap"],
                },
            ],
            "probe_seeds": [
                "A user posts a comment and does not see it after refreshing. Which guarantee was missing?",
                "During a partition, what are the only two things a replica can do about a write?",
                "What does strong consistency cost on every single request, partition or not?",
            ],
            "challenge_seeds": [
                "A user updates their profile photo and the old one reappears on refresh. Name the guarantee that was violated and the cheapest fix.",
                "Choose a consistency model for a bank balance and for a like count. Justify each in terms of what the user experiences when it is wrong.",
                "Your system must serve reads from three continents with a 100ms budget. Explain what that rules out and what user-visible anomalies you are accepting.",
            ],
            "chunks": [
                (
                    "Strong consistency requires replicas to agree before acknowledging, so "
                    "every operation pays at least one round trip to a quorum. That cost is "
                    "paid on healthy days, not only during failures."
                ),
                (
                    "Session guarantees — read-your-writes, monotonic reads — remove the "
                    "anomalies users actually notice, because a user compares against their own "
                    "history, not against a global timeline."
                ),
            ],
        },
        {
            "slug": "consensus",
            "title": "Consensus",
            "one_liner": "Getting independent machines to agree on one value.",
            "difficulty": 0.8,
            "bloom_ceiling": "analyze",
            "position": (4, 0),
            "canonical_model": (
                "Consensus is the problem of making a group of nodes agree on a single value "
                "despite failures and unreliable messaging. Practical protocols use majority "
                "quorums: any two majorities of the same group intersect, so a decision cannot "
                "be made twice with different values. This is why an odd number of nodes is "
                "preferred, and why a five-node cluster tolerates two failures while a "
                "four-node cluster also tolerates only one. Consensus is expensive — it costs "
                "round trips on the critical path — so well-designed systems use it sparingly, "
                "typically for metadata, leader election and configuration, and keep the "
                "high-volume data path out of it. It cannot be solved with a guarantee of "
                "termination in a fully asynchronous system with even one faulty node, which "
                "is why every real protocol relies on timeouts and accepts that it may stall "
                "rather than ever being wrong."
            ),
            "misconception_bank": [
                {
                    "claim": "more nodes make a consensus cluster more reliable",
                    "canonical": (
                        "More nodes tolerate more failures but make every decision slower, and "
                        "even numbers add no fault tolerance over the odd number below them."
                    ),
                    "severity": "medium",
                    "triggers": ["more nodes", "more replicas", "add nodes", "bigger cluster"],
                },
                {
                    "claim": "a leader guarantees there is only one leader",
                    "canonical": (
                        "A partitioned old leader can still believe it leads. Correctness comes "
                        "from quorum intersection and fencing terms, not from the role itself."
                    ),
                    "severity": "high",
                    "triggers": [
                        "single leader",
                        "only one leader",
                        "leader election",
                        "the leader",
                    ],
                },
            ],
            "probe_seeds": [
                "Why can two majorities of the same five nodes never be disjoint?",
                "A five-node cluster loses three nodes. What can the remaining two safely do?",
                "The old leader has not noticed it was replaced. What stops its writes from being accepted?",
            ],
            "challenge_seeds": [
                "Explain why a four-node consensus cluster tolerates no more failures than a three-node one.",
                "A partitioned leader keeps accepting writes for 30 seconds. Explain what prevents those writes from corrupting the log.",
                "Your team proposes routing every user request through Raft for 'safety'. Argue the case against, quantitatively, and say what you would put through it instead.",
            ],
            "chunks": [
                (
                    "Quorum intersection is the whole trick. In a group of five, any two sets of "
                    "three share at least one member, and that member remembers the earlier "
                    "decision — so a conflicting second decision cannot be reached."
                ),
                (
                    "Fencing tokens make stale leaders harmless: every decision carries a "
                    "monotonically increasing term, and followers reject anything from an older "
                    "term. The deposed leader can keep trying; nobody listens."
                ),
            ],
        },
    ],
    "edges": [
        ("latency", "partial-failure"),
        ("partial-failure", "idempotency"),
        ("partial-failure", "consistency"),
        ("consistency", "consensus"),
        ("idempotency", "consistency"),
    ],
}


CURRICULA: list[dict[str, Any]] = [NEURAL_NETWORKS, STATISTICS, DISTRIBUTED]

__all__ = ["CURRICULA", "DISTRIBUTED", "NEURAL_NETWORKS", "STATISTICS"]
