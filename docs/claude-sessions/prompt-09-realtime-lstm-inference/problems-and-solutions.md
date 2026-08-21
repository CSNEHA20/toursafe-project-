# Problems and Solutions — Prompt 9: Real-Time LSTM Inference Service

## Problem 1: Telemetry Schema Naming Mismatch in Test Suite
- **Problem**: `ImportError: cannot import name 'AccelerometerReading' from 'app.schemas.telemetry'` during initial test collection.
- **Cause**: Prompt 7 telemetry schema named the component models `AccelerometerChannels` and `GyroscopeChannels` rather than `AccelerometerReading`.
- **Solution**: Updated test suite helper to use `AccelerometerChannels` and `GyroscopeChannels`.
- **Verification**: `python -m pytest tests/test_ml_inference.py` collected and executed 18/18 tests successfully.

## Problem 2: Standalone Execution Python Path in Benchmark Script
- **Problem**: `ModuleNotFoundError: No module named 'app'` when running `python tests/benchmark_inference.py`.
- **Cause**: Executing script directly in Python without `PYTHONPATH=.` set in environment.
- **Solution**: Added automatic `sys.path.insert(0, str(backend_dir))` in the benchmark script header.
- **Verification**: `python tests/benchmark_inference.py` executed cleanly without import errors.

## Problem 3: Unicode Character Encoding on Windows Console
- **Problem**: `UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f4ca'` on Windows `cp1252` terminal.
- **Cause**: Benchmark script used emoji icons in `print()` statements which were rejected by the default Windows console encoding.
- **Solution**: Replaced unicode emojis with standard ASCII bracket headers `[BENCHMARK]`.
- **Verification**: Benchmark script printed full latency percentiles and throughput metrics without encoding exceptions.
