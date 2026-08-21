"""
TourSafe ML Inference Latency and Concurrency Load Benchmark.
Executes rigorous performance profiling on the real-time inference pipeline:
- Latency percentiles (mean, p50, p95, p99)
- Inference throughput (windows/second)
- Concurrency simulation (1, 5, 10 concurrent tourists generating 3s windows)
"""

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import time
import numpy as np

# Ensure backend root is in sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.schemas.telemetry import (
    AccelerometerChannels,
    GPSPayload,
    GyroscopeChannels,
    QualityMetrics,
    QualityStateEnum,
    TelemetrySample,
    TelemetryWindow,
)
from app.services.ml.engine import ml_inference_engine
from app.services.ml.loader import model_loader


def generate_benchmark_window(tourist_id: str, session_id: str) -> TelemetryWindow:
    start_dt = datetime.now(timezone.utc) - timedelta(seconds=3.0)
    samples = []
    for i in range(150):
        s_time = (start_dt + timedelta(seconds=i * 0.02)).isoformat()
        samples.append(
            TelemetrySample(
                packet_id=f"pkt_bench_{i}",
                session_id=session_id,
                tourist_id=tourist_id,
                device_id="dev_bench_01",
                sequence_number=i + 1,
                timestamp=s_time,
                accelerometer=AccelerometerChannels(
                    x=float(0.1 * np.sin(i * 0.1)),
                    y=float(0.98 + 0.05 * np.cos(i * 0.1)),
                    z=float(0.02 * np.sin(i * 0.2)),
                ),
                gyroscope=GyroscopeChannels(
                    x=float(0.01 * np.sin(i * 0.1)),
                    y=float(0.02 * np.cos(i * 0.1)),
                    z=float(0.005 * np.sin(i * 0.1)),
                ),
            )
        )

    return TelemetryWindow(
        window_id=f"win_bench_{time.time_ns()}",
        session_id=session_id,
        tourist_id=tourist_id,
        device_id="dev_bench_01",
        window_start=start_dt.isoformat(),
        window_end=(start_dt + timedelta(seconds=3.0)).isoformat(),
        duration_seconds=3.0,
        stride_seconds=1.0,
        sample_count=150,
        observed_frequency_hz=50.0,
        completeness_ratio=1.0,
        is_valid=True,
        validation_errors=[],
        quality=QualityMetrics(
            gps_quality=QualityStateEnum.GOOD,
            imu_quality=QualityStateEnum.GOOD,
            synchronization_quality=QualityStateEnum.EXCELLENT,
            network_quality=QualityStateEnum.EXCELLENT,
            overall_quality=QualityStateEnum.GOOD,
            observed_frequency_hz=50.0,
        ),
        samples=samples,
        gps_context=GPSPayload(latitude=10.2381, longitude=77.4892, accuracy=5.0),
        created_at=datetime.now(timezone.utc).isoformat(),
    )


async def run_latency_profile(num_iterations: int = 150):
    print(f"\n============================================================")
    print(f"[BENCHMARK] 1. SINGLE-STREAM INFERENCE LATENCY PROFILING ({num_iterations} windows)")
    print(f"============================================================")

    model_loader.load_and_validate("v1.0.0")

    latencies_total = []
    latencies_prep = []
    latencies_model = []
    latencies_post = []

    # Warmup
    for _ in range(10):
        w = generate_benchmark_window("tourist_warmup", "sess_warmup")
        await ml_inference_engine.process_single_window(w)

    for i in range(num_iterations):
        w = generate_benchmark_window(f"tourist_bench_{i % 5}", f"sess_bench_{i % 5}")
        res = await ml_inference_engine.process_single_window(w)
        if res.latency:
            latencies_prep.append(res.latency.preprocessing_ms)
            latencies_model.append(res.latency.model_inference_ms)
            latencies_post.append(res.latency.postprocessing_ms)
            latencies_total.append(res.latency.total_inference_ms)

    arr_tot = np.array(latencies_total)
    arr_prep = np.array(latencies_prep)
    arr_mod = np.array(latencies_model)
    arr_post = np.array(latencies_post)

    print(f"Preprocessing Latency   -> Mean: {np.mean(arr_prep):.2f}ms | p50: {np.percentile(arr_prep, 50):.2f}ms | p95: {np.percentile(arr_prep, 95):.2f}ms | p99: {np.percentile(arr_prep, 99):.2f}ms")
    print(f"Model Inference Latency -> Mean: {np.mean(arr_mod):.2f}ms | p50: {np.percentile(arr_mod, 50):.2f}ms | p95: {np.percentile(arr_mod, 95):.2f}ms | p99: {np.percentile(arr_mod, 99):.2f}ms")
    print(f"Postprocessing Latency  -> Mean: {np.mean(arr_post):.2f}ms | p50: {np.percentile(arr_post, 50):.2f}ms | p95: {np.percentile(arr_post, 95):.2f}ms | p99: {np.percentile(arr_post, 99):.2f}ms")
    print(f"------------------------------------------------------------")
    print(f"TOTAL Inference Latency -> Mean: {np.mean(arr_tot):.2f}ms | p50: {np.percentile(arr_tot, 50):.2f}ms | p95: {np.percentile(arr_tot, 95):.2f}ms | p99: {np.percentile(arr_tot, 99):.2f}ms")

    return {
        "mean_ms": float(np.mean(arr_tot)),
        "p50_ms": float(np.percentile(arr_tot, 50)),
        "p95_ms": float(np.percentile(arr_tot, 95)),
        "p99_ms": float(np.percentile(arr_tot, 99)),
    }


async def run_throughput_benchmark(duration_sec: float = 3.0):
    print(f"\n============================================================")
    print(f"[BENCHMARK] 2. MAXIMAL INFERENCE THROUGHPUT BENCHMARK ({duration_sec}s test)")
    print(f"============================================================")

    count = 0
    t_start = time.time()
    while (time.time() - t_start) < duration_sec:
        w = generate_benchmark_window("tourist_thru", "sess_thru")
        await ml_inference_engine.process_single_window(w)
        count += 1
    t_end = time.time()

    elapsed = t_end - t_start
    rate = count / elapsed
    print(f"Processed {count} windows in {elapsed:.2f}s -> {rate:.1f} windows/second")
    return rate


async def simulate_tourist_stream(tourist_id: str, num_windows: int, stride_sec: float = 1.0):
    for i in range(num_windows):
        w = generate_benchmark_window(tourist_id, f"sess_{tourist_id}")
        await ml_inference_engine.process_single_window(w)
        await asyncio.sleep(0.01)  # small yield


async def run_concurrent_load_test(concurrency_levels=(1, 5, 10)):
    print(f"\n============================================================")
    print(f"[BENCHMARK] 3. CONCURRENT TOURIST LOAD SIMULATION")
    print(f"============================================================")

    for n_tourists in concurrency_levels:
        windows_per_tourist = 15
        t_start = time.time()
        tasks = [
            simulate_tourist_stream(f"tourist_load_{idx}", windows_per_tourist)
            for idx in range(n_tourists)
        ]
        await asyncio.gather(*tasks)
        elapsed = time.time() - t_start
        total_windows = n_tourists * windows_per_tourist
        rate = total_windows / elapsed
        print(f"Concurrency {n_tourists:2d} Tourists -> {total_windows} windows in {elapsed:.2f}s ({rate:.1f} win/s) | Errors: 0")


async def main():
    await run_latency_profile(100)
    await run_throughput_benchmark(3.0)
    await run_concurrent_load_test((1, 5, 10))


if __name__ == "__main__":
    asyncio.run(main())
