"""
Step 4: Split the job data into two chunks.

Takes job.npz (540 images) and splits it into two smaller files,
simulating what would go to two separate computers. We also save
the original index of each image, so we can put everything back
in the correct order later when combining results.
"""

import numpy as np

def main():
    data = np.load("job.npz")
    X_job, y_job = data["X"], data["y"]

    num_samples = X_job.shape[0]
    split_point = num_samples // 2  #cuts the pile in half

    #We keep the original index numbers, so we know the correct order when merging
    indices = np.arange(num_samples)

    X_part1, y_part1, idx_part1 = X_job[:split_point], y_job[:split_point], indices[:split_point]
    X_part2, y_part2, idx_part2 = X_job[split_point:], y_job[split_point:], indices[split_point:]

    np.savez("job_part1.npz", X=X_part1, y=y_part1, original_index=idx_part1) #creates job_part1.npz
    np.savez("job_part2.npz", X=X_part2, y=y_part2, original_index=idx_part2) #creates job_part2.npz

    print(f"Part 1: {X_part1.shape[0]} samples -> job_part1.npz")
    print(f"Part 2: {X_part2.shape[0]} samples -> job_part2.npz")

if __name__ == "__main__":
    main()