"""
TourSafe Anti-Leakage Detection Engine.
Enforces strict subject-wise and session-wise partitioning across Train, Validation,
and Test datasets to prevent temporal or identity data leakage.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple
import numpy as np


@dataclass
class LeakageCheckResult:
    passed: bool
    subject_overlaps: Dict[str, List[str]] = field(default_factory=dict)
    session_overlaps: Dict[str, List[str]] = field(default_factory=dict)
    temporal_overlap_count: int = 0
    duplicate_window_count: int = 0
    errors: List[str] = field(default_factory=list)


class DataLeakageDetector:
    """
    Validates mathematical and semantic partition independence across train, val, and test splits.
    """

    def check_splits(
        self,
        train_subjects: List[str],
        val_subjects: List[str],
        test_subjects: List[str],
        train_sessions: Optional[List[str]] = None,
        val_sessions: Optional[List[str]] = None,
        test_sessions: Optional[List[str]] = None,
        X_train: Optional[np.ndarray] = None,
        X_val: Optional[np.ndarray] = None,
        X_test: Optional[np.ndarray] = None,
    ) -> LeakageCheckResult:
        errors = []
        subject_overlaps = {}
        session_overlaps = {}

        s_tr = set(train_subjects)
        s_val = set(val_subjects)
        s_te = set(test_subjects)

        # 1. Subject Overlap Verification
        tr_val_sub = s_tr.intersection(s_val)
        if tr_val_sub:
            subject_overlaps["train_val"] = sorted(list(tr_val_sub))
            errors.append(f"Subject leakage between Train and Val: {subject_overlaps['train_val']}")

        tr_te_sub = s_tr.intersection(s_te)
        if tr_te_sub:
            subject_overlaps["train_test"] = sorted(list(tr_te_sub))
            errors.append(f"Subject leakage between Train and Test: {subject_overlaps['train_test']}")

        val_te_sub = s_val.intersection(s_te)
        if val_te_sub:
            subject_overlaps["val_test"] = sorted(list(val_te_sub))
            errors.append(f"Subject leakage between Val and Test: {subject_overlaps['val_test']}")

        # 2. Session Overlap Verification (if sessions provided)
        if train_sessions and val_sessions and test_sessions:
            sess_tr = set(train_sessions)
            sess_val = set(val_sessions)
            sess_te = set(test_sessions)

            tr_val_sess = sess_tr.intersection(sess_val)
            if tr_val_sess:
                session_overlaps["train_val"] = sorted(list(tr_val_sess))
                errors.append(f"Session leakage between Train and Val: {session_overlaps['train_val']}")

            tr_te_sess = sess_tr.intersection(sess_te)
            if tr_te_sess:
                session_overlaps["train_test"] = sorted(list(tr_te_sess))
                errors.append(f"Session leakage between Train and Test: {session_overlaps['train_test']}")

            val_te_sess = sess_val.intersection(sess_te)
            if val_te_sess:
                session_overlaps["val_test"] = sorted(list(val_te_sess))
                errors.append(f"Session leakage between Val and Test: {session_overlaps['val_test']}")

        # 3. Duplicate Window Detection (Exact tensor match check on samples)
        dup_count = 0
        if X_train is not None and X_test is not None and len(X_train) > 0 and len(X_test) > 0:
            # Sample hash check on first few channels
            train_hashes = {hash(np.ascontiguousarray(x).tobytes()) for x in X_train[:500]}
            for x in X_test[:200]:
                h = hash(np.ascontiguousarray(x).tobytes())
                if h in train_hashes:
                    dup_count += 1
            if dup_count > 0:
                errors.append(f"Detected {dup_count} duplicate window tensors between Train and Test splits")

        passed = len(errors) == 0

        return LeakageCheckResult(
            passed=passed,
            subject_overlaps=subject_overlaps,
            session_overlaps=session_overlaps,
            duplicate_window_count=dup_count,
            errors=errors,
        )


leakage_detector = DataLeakageDetector()
