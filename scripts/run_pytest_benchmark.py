from pathlib import Path
import subprocess
import time

PROJECT_ROOT = Path(__file__).resolve().parent.parent
assert (PROJECT_ROOT / "frequencyman").is_dir()

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
            check=False
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

    result_summary_txt = "\n"
    result_summary_txt += "Summary over {} runs:\n".format(runs)
    result_summary_txt += "  Total time: {:.0f} seconds\n".format(total)
    result_summary_txt += "  Average time (fastest 50%): {:.1f} seconds\n".format(avg)
    result_summary_txt += "  Minimum time: {:.1f} seconds\n".format(min_time)

    print(result_summary_txt)

    # add to log file
    log_file = PROJECT_ROOT / 'pytest_benchmark.tmp.log'
    with log_file.open("a") as f:
        f.write(result_summary_txt+"\n")

if __name__ == "__main__":
    main()
