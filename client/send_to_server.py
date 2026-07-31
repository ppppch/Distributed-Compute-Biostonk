"""
Client computer - sends the second chunk to the remote server.

Loads job_part2.npz, posts the images and original indices to the
server's /predict endpoint, and saves the returned predictions as
results_part2.npz. This lets the second machine do the inference
while this client only ever sees part 2.
"""

import argparse
import numpy as np
import requests

DEFAULT_URL = "http://127.0.0.1:8000/predict"


def main(url: str) -> None:
    #load this computer's chunk that will be processed remotely
    data = np.load("job_part2.npz")
    X_part = data["X"]
    original_index = data["original_index"]

    #send the chunk to the server and ask for predictions back
    payload = {
        "images": X_part.tolist(),
        "original_index": original_index.tolist(),
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()

    result = response.json()
    predictions = np.array(result["predictions"])
    returned_index = np.array(result["original_index"])

    np.savez(
        "results_part2.npz",
        predictions=predictions,
        original_index=returned_index,
    )

    print(f"Sent {X_part.shape[0]} samples to {url} (Part 2)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Send job_part2.npz to the inference server."
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Server predict endpoint (default: {DEFAULT_URL})",
    )
    args = parser.parse_args()
    main(args.url)
