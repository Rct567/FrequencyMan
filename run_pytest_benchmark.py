import subprocess
import time

def main() -> None:
    runs = 30
    durations: list[float] = []

    for i in range(runs):
        print("Run {} of {}... ".format(i + 1, runs), end="")
        start = time.perf_counter()

        result = subprocess.run(
            ["pytest", "-q", "-k", "target_list_reorder"],
            capture_output=True,
            text=True,
        )

        elapsed = time.perf_counter() - start
        durations.append(elapsed)
        print("  {:.2f} seconds".format(elapsed))

        if result.returncode != 0:
            print("❌ Test failed on run {}!".format(i + 1))
            print("---- pytest output ----")
            print(result.stdout)
            print(result.stderr)
            return  # stop immediately


    sorted_durations = sorted(durations)
    top_count = len(sorted_durations) // 2
    top_durations = sorted_durations[:top_count]

    total = sum(durations)
    avg = sum(top_durations) / len(top_durations)
    min_time = min(durations)

    result = "\n"
    result += "Summary over {} runs:\n".format(runs)
    result += "  Total time: {:.0f} seconds\n".format(total)
    result += "  Average time (fastest 50%): {:.1f} seconds\n".format(avg)
    result += "  Minimum time: {:.1f} seconds\n".format(min_time)

    print(result)

    # add to log file
    with open("pytest_benchmark.tmp.log", "a") as f:
        f.write(result+"\n")

if __name__ == "__main__":
    main()
