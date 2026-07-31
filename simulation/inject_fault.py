"""
Inject a controlled fault into a worker result.

Loads results_part1.npz, flips exactly one prediction to a different
digit, and saves it back. This simulates a bad/mismatched chunk result
so combine_and_verify.py can demonstrate rejection.
"""

import numpy as np


def main():
    data = np.load("results_part1.npz")
    predictions = data["predictions"].copy()
    original_index = data["original_index"].copy()

    # Flip the first prediction to a different digit value.
    original_value = int(predictions[0])
    new_value = (original_value + 1) % 10
    predictions[0] = new_value

    np.savez(
        "results_part1.npz",
        predictions=predictions,
        original_index=original_index,
    )

    print(
        f"Injected fault: result at position 0 changed from {original_value} to {new_value}"
    )


if __name__ == "__main__":
    main()
