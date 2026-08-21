"""
TourSafe Synthetic IMU Telemetry Generator.
Generates biomechanically grounded, high-fidelity multi-subject IMU sensor data
for normal tourist Activities of Daily Living (ADLs) and anomalous dynamic events.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union
import numpy as np


@dataclass
class ActivityProfile:
    name: str
    is_anomaly: bool
    duration_range_sec: Tuple[float, float]
    base_accel_hz: float
    accel_amp_g: float
    gyro_amp_rads: float
    gravity_alignment: Tuple[float, float, float]  # (gx, gy, gz) in rest orientation
    noise_std: float = 0.02


NORMAL_ACTIVITIES: Dict[str, ActivityProfile] = {
    "walking": ActivityProfile(
        name="walking",
        is_anomaly=False,
        duration_range_sec=(20.0, 60.0),
        base_accel_hz=1.6,
        accel_amp_g=0.35,
        gyro_amp_rads=0.6,
        gravity_alignment=(0.1, 0.9, 0.2),
        noise_std=0.03,
    ),
    "brisk_walking": ActivityProfile(
        name="brisk_walking",
        is_anomaly=False,
        duration_range_sec=(15.0, 45.0),
        base_accel_hz=2.0,
        accel_amp_g=0.55,
        gyro_amp_rads=0.9,
        gravity_alignment=(0.15, 0.92, 0.18),
        noise_std=0.04,
    ),
    "jogging": ActivityProfile(
        name="jogging",
        is_anomaly=False,
        duration_range_sec=(15.0, 30.0),
        base_accel_hz=2.7,
        accel_amp_g=1.2,
        gyro_amp_rads=1.8,
        gravity_alignment=(0.1, 0.9, 0.25),
        noise_std=0.06,
    ),
    "standing": ActivityProfile(
        name="standing",
        is_anomaly=False,
        duration_range_sec=(15.0, 40.0),
        base_accel_hz=0.2,  # low frequency postural sway
        accel_amp_g=0.03,
        gyro_amp_rads=0.04,
        gravity_alignment=(0.02, 0.98, 0.05),
        noise_std=0.015,
    ),
    "sitting": ActivityProfile(
        name="sitting",
        is_anomaly=False,
        duration_range_sec=(20.0, 50.0),
        base_accel_hz=0.1,
        accel_amp_g=0.02,
        gyro_amp_rads=0.02,
        gravity_alignment=(0.0, 0.7, 0.7),
        noise_std=0.01,
    ),
    "stairs_ascent": ActivityProfile(
        name="stairs_ascent",
        is_anomaly=False,
        duration_range_sec=(15.0, 35.0),
        base_accel_hz=1.2,
        accel_amp_g=0.5,
        gyro_amp_rads=0.7,
        gravity_alignment=(0.1, 0.95, 0.15),
        noise_std=0.04,
    ),
    "stairs_descent": ActivityProfile(
        name="stairs_descent",
        is_anomaly=False,
        duration_range_sec=(15.0, 35.0),
        base_accel_hz=1.4,
        accel_amp_g=0.7,
        gyro_amp_rads=0.8,
        gravity_alignment=(0.12, 0.94, 0.16),
        noise_std=0.045,
    ),
    "transit_bus": ActivityProfile(
        name="transit_bus",
        is_anomaly=False,
        duration_range_sec=(25.0, 60.0),
        base_accel_hz=0.4,
        accel_amp_g=0.15,
        gyro_amp_rads=0.15,
        gravity_alignment=(0.05, 0.85, 0.5),
        noise_std=0.03,
    ),
}

ANOMALOUS_ACTIVITIES: Dict[str, ActivityProfile] = {
    "forward_fall": ActivityProfile(
        name="forward_fall",
        is_anomaly=True,
        duration_range_sec=(8.0, 15.0),
        base_accel_hz=0.0,
        accel_amp_g=5.5,
        gyro_amp_rads=5.0,
        gravity_alignment=(0.1, 0.9, 0.2),
        noise_std=0.05,
    ),
    "backward_fall": ActivityProfile(
        name="backward_fall",
        is_anomaly=True,
        duration_range_sec=(8.0, 15.0),
        base_accel_hz=0.0,
        accel_amp_g=6.0,
        gyro_amp_rads=5.5,
        gravity_alignment=(0.1, 0.9, 0.2),
        noise_std=0.05,
    ),
    "lateral_fall": ActivityProfile(
        name="lateral_fall",
        is_anomaly=True,
        duration_range_sec=(8.0, 15.0),
        base_accel_hz=0.0,
        accel_amp_g=4.8,
        gyro_amp_rads=4.5,
        gravity_alignment=(0.1, 0.9, 0.2),
        noise_std=0.05,
    ),
    "sudden_collapse": ActivityProfile(
        name="sudden_collapse",
        is_anomaly=True,
        duration_range_sec=(8.0, 15.0),
        base_accel_hz=0.0,
        accel_amp_g=3.8,
        gyro_amp_rads=3.5,
        gravity_alignment=(0.1, 0.9, 0.2),
        noise_std=0.04,
    ),
    "violent_shaking": ActivityProfile(
        name="violent_shaking",
        is_anomaly=True,
        duration_range_sec=(6.0, 12.0),
        base_accel_hz=8.0,
        accel_amp_g=4.2,
        gyro_amp_rads=6.0,
        gravity_alignment=(0.1, 0.9, 0.2),
        noise_std=0.08,
    ),
    "vehicle_collision_shock": ActivityProfile(
        name="vehicle_collision_shock",
        is_anomaly=True,
        duration_range_sec=(6.0, 12.0),
        base_accel_hz=0.0,
        accel_amp_g=7.5,
        gyro_amp_rads=7.0,
        gravity_alignment=(0.1, 0.85, 0.4),
        noise_std=0.06,
    ),
}


class SyntheticIMUGenerator:
    """
    Simulates high-fidelity multi-subject continuous IMU telemetry streams
    with realistic physical kinematics, subject biomechanical variations,
    and mobile sensor jitter.
    """

    def __init__(self, target_hz: float = 50.0, random_seed: int = 42):
        self.target_hz = target_hz
        self.dt = 1.0 / target_hz
        self.rng = np.random.default_rng(random_seed)

    def _generate_normal_signal(
        self,
        profile: ActivityProfile,
        duration_sec: float,
        subject_factor: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates continuous normal periodic or quasi-static ADL kinematic time series.
        """
        n_steps = int(round(duration_sec * self.target_hz))
        # Add realistic temporal jitter (±3ms)
        jitter = self.rng.normal(0.0, 0.003, size=n_steps)
        t = np.cumsum(np.full(n_steps, self.dt) + jitter)
        t -= t[0]

        freq = profile.base_accel_hz * subject_factor
        amp_a = profile.accel_amp_g * subject_factor
        amp_g = profile.gyro_amp_rads * subject_factor

        # Normalized gravity vector
        gx, gy, gz = profile.gravity_alignment
        g_norm = np.sqrt(gx**2 + gy**2 + gz**2)
        gx, gy, gz = gx / g_norm, gy / g_norm, gz / g_norm

        if freq > 0.3:
            # Periodic locomotion (walking, stairs, jogging)
            # Vertical oscillation with harmonics
            harmonic_1 = np.sin(2 * np.pi * freq * t)
            harmonic_2 = 0.35 * np.sin(4 * np.pi * freq * t + np.pi / 4)
            step_signal = harmonic_1 + harmonic_2

            # Accelerations (g)
            ax = 0.25 * amp_a * np.sin(2 * np.pi * freq * t + np.pi / 2) + gx
            ay = amp_a * step_signal + gy
            az = 0.4 * amp_a * np.cos(2 * np.pi * freq * t) + gz

            # Angular velocities (rad/s)
            gyro_x = amp_g * np.sin(2 * np.pi * freq * t)
            gyro_y = 0.4 * amp_g * np.cos(2 * np.pi * freq * t)
            gyro_z = 0.3 * amp_g * np.sin(4 * np.pi * freq * t)
        else:
            # Low-frequency quasi-static posture (standing, sitting, transit)
            sway_x = 0.02 * np.sin(2 * np.pi * freq * t)
            sway_z = 0.02 * np.cos(2 * np.pi * freq * t)

            ax = gx + sway_x
            ay = gy + 0.01 * np.sin(2 * np.pi * (freq * 1.5) * t)
            az = gz + sway_z

            gyro_x = amp_g * np.sin(2 * np.pi * freq * t)
            gyro_y = amp_g * np.cos(2 * np.pi * freq * t)
            gyro_z = 0.5 * amp_g * np.sin(2 * np.pi * (freq * 0.7) * t)

        # Add Gaussian sensor noise and slight brownian drift
        noise_a = self.rng.normal(0, profile.noise_std, size=(n_steps, 3))
        noise_g = self.rng.normal(0, profile.noise_std * 1.2, size=(n_steps, 3))

        accel = np.stack([ax, ay, az], axis=1) + noise_a
        gyro = np.stack([gyro_x, gyro_y, gyro_z], axis=1) + noise_g

        return t, accel, gyro

    def _generate_anomalous_signal(
        self,
        profile: ActivityProfile,
        duration_sec: float,
        subject_factor: float,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Generates anomalous movement time-series containing biomechanical fall phases:
        1. Pre-fall normal movement (1.5s - 3.0s)
        2. Weightlessness / Free-fall descent (0.15s - 0.35s)
        3. High-G impact peak + rotational torque burst (0.1s - 0.25s)
        4. Post-fall rest / irregular recovery posture (remainder)
        """
        n_steps = int(round(duration_sec * self.target_hz))
        jitter = self.rng.normal(0.0, 0.003, size=n_steps)
        t = np.cumsum(np.full(n_steps, self.dt) + jitter)
        t -= t[0]

        # Phase timing (event anchored around 30-50% of sequence)
        event_start_t = duration_sec * self.rng.uniform(0.3, 0.5)
        freefall_dur = self.rng.uniform(0.18, 0.32)
        impact_dur = self.rng.uniform(0.12, 0.22)

        t_freefall_end = event_start_t + freefall_dur
        t_impact_end = t_freefall_end + impact_dur

        # Initialize base posture
        gx, gy, gz = profile.gravity_alignment
        ax = np.full(n_steps, gx)
        ay = np.full(n_steps, gy)
        az = np.full(n_steps, gz)
        gyro_x = np.zeros(n_steps)
        gyro_y = np.zeros(n_steps)
        gyro_z = np.zeros(n_steps)

        # Pre-event walking oscillation
        pre_mask = t < event_start_t
        ax[pre_mask] += 0.25 * np.sin(2 * np.pi * 1.5 * t[pre_mask])
        ay[pre_mask] += 0.35 * np.sin(2 * np.pi * 3.0 * t[pre_mask])
        az[pre_mask] += 0.20 * np.cos(2 * np.pi * 1.5 * t[pre_mask])
        gyro_x[pre_mask] += 0.4 * np.sin(2 * np.pi * 1.5 * t[pre_mask])

        if profile.name in ("forward_fall", "backward_fall", "lateral_fall", "sudden_collapse"):
            # 1. Freefall phase: total acceleration magnitude drops toward 0.1-0.3g
            ff_mask = (t >= event_start_t) & (t < t_freefall_end)
            if np.any(ff_mask):
                decay = np.linspace(1.0, 0.15, np.sum(ff_mask))
                ax[ff_mask] *= decay
                ay[ff_mask] *= decay
                az[ff_mask] *= decay
                # Angular velocity builds up during tumble
                gyro_x[ff_mask] = np.linspace(0.5, profile.gyro_amp_rads * 0.7, np.sum(ff_mask))

            # 2. Impact phase: High-G pulse (damping sinusoid)
            imp_mask = (t >= t_freefall_end) & (t < t_impact_end)
            if np.any(imp_mask):
                t_imp = t[imp_mask] - t_freefall_end
                pulse = np.exp(-t_imp * 20.0) * np.sin(2 * np.pi * 12.0 * t_imp)
                peak_g = profile.accel_amp_g * subject_factor

                if profile.name == "forward_fall":
                    ax[imp_mask] = peak_g * 0.4 * pulse
                    ay[imp_mask] = peak_g * pulse
                    az[imp_mask] = peak_g * 0.7 * pulse
                    gyro_y[imp_mask] = profile.gyro_amp_rads * pulse
                elif profile.name == "backward_fall":
                    ax[imp_mask] = peak_g * 0.3 * pulse
                    ay[imp_mask] = -peak_g * pulse
                    az[imp_mask] = -peak_g * 0.8 * pulse
                    gyro_x[imp_mask] = -profile.gyro_amp_rads * pulse
                elif profile.name == "lateral_fall":
                    ax[imp_mask] = peak_g * pulse
                    ay[imp_mask] = peak_g * 0.5 * pulse
                    az[imp_mask] = peak_g * 0.4 * pulse
                    gyro_z[imp_mask] = profile.gyro_amp_rads * pulse
                else:  # collapse
                    ax[imp_mask] = peak_g * 0.5 * pulse
                    ay[imp_mask] = peak_g * 0.8 * pulse
                    az[imp_mask] = peak_g * 0.5 * pulse

            # 3. Post-fall resting on ground (new gravity vector orientation)
            post_mask = t >= t_impact_end
            if np.any(post_mask):
                # New orientation resting on ground (e.g. lying flat: z ≈ 0.95g, y ≈ 0.1g)
                ax[post_mask] = 0.1 + self.rng.normal(0, 0.02, np.sum(post_mask))
                ay[post_mask] = 0.15 + self.rng.normal(0, 0.02, np.sum(post_mask))
                az[post_mask] = 0.95 + self.rng.normal(0, 0.02, np.sum(post_mask))
                gyro_x[post_mask] = self.rng.normal(0, 0.03, np.sum(post_mask))
                gyro_y[post_mask] = self.rng.normal(0, 0.03, np.sum(post_mask))
                gyro_z[post_mask] = self.rng.normal(0, 0.03, np.sum(post_mask))

        elif profile.name == "violent_shaking":
            # Continuous multi-axis erratic vibrations
            shock_mask = (t >= event_start_t) & (t < event_start_t + 5.0)
            if np.any(shock_mask):
                t_sh = t[shock_mask] - event_start_t
                ax[shock_mask] += profile.accel_amp_g * np.sin(2 * np.pi * 9.0 * t_sh + 0.3)
                ay[shock_mask] += profile.accel_amp_g * np.sin(2 * np.pi * 11.5 * t_sh + 1.2)
                az[shock_mask] += profile.accel_amp_g * np.sin(2 * np.pi * 7.5 * t_sh + 2.5)
                gyro_x[shock_mask] += profile.gyro_amp_rads * np.cos(2 * np.pi * 8.0 * t_sh)
                gyro_y[shock_mask] += profile.gyro_amp_rads * np.sin(2 * np.pi * 10.0 * t_sh)
                gyro_z[shock_mask] += profile.gyro_amp_rads * np.cos(2 * np.pi * 12.0 * t_sh)

        elif profile.name == "vehicle_collision_shock":
            # Instantaneous extreme deceleration spike (>6g)
            shock_mask = (t >= event_start_t) & (t < event_start_t + 0.35)
            if np.any(shock_mask):
                t_sh = t[shock_mask] - event_start_t
                pulse = np.exp(-t_sh * 15.0) * np.sin(2 * np.pi * 20.0 * t_sh)
                ay[shock_mask] -= profile.accel_amp_g * pulse
                ax[shock_mask] += (profile.accel_amp_g * 0.4) * pulse
                gyro_z[shock_mask] += profile.gyro_amp_rads * pulse

        noise_a = self.rng.normal(0, profile.noise_std, size=(n_steps, 3))
        noise_g = self.rng.normal(0, profile.noise_std * 1.2, size=(n_steps, 3))

        accel = np.stack([ax, ay, az], axis=1) + noise_a
        gyro = np.stack([gyro_x, gyro_y, gyro_z], axis=1) + noise_g

        return t, accel, gyro

    def generate_subject_session(
        self,
        subject_id: str,
        include_anomalies: bool = False,
        normal_repeats_per_activity: int = 2,
        anomaly_repeats_per_activity: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Generates a full telemetry recording session for a single subject containing
        multiple activity trials with distinct subject physical scaling factors.
        """
        # Subject biomechanical factor (e.g. cadence variation, height/weight inertia ±15%)
        subject_factor = float(self.rng.uniform(0.88, 1.14))
        trials: List[Dict[str, Any]] = []

        # 1. Normal Activities
        for act_name, profile in NORMAL_ACTIVITIES.items():
            for rep in range(normal_repeats_per_activity):
                duration = float(self.rng.uniform(*profile.duration_range_sec))
                t, accel, gyro = self._generate_normal_signal(profile, duration, subject_factor)
                trials.append({
                    "subject_id": subject_id,
                    "activity": act_name,
                    "is_anomaly": False,
                    "trial_id": f"{subject_id}_{act_name}_rep{rep+1}",
                    "timestamps_sec": t,
                    "accel": accel,  # (N, 3) [ax, ay, az] in g
                    "gyro": gyro,    # (N, 3) [gx, gy, gz] in rad/s
                })

        # 2. Anomalous Activities (if requested for test evaluation)
        if include_anomalies:
            for act_name, profile in ANOMALOUS_ACTIVITIES.items():
                for rep in range(anomaly_repeats_per_activity):
                    duration = float(self.rng.uniform(*profile.duration_range_sec))
                    t, accel, gyro = self._generate_anomalous_signal(profile, duration, subject_factor)
                    trials.append({
                        "subject_id": subject_id,
                        "activity": act_name,
                        "is_anomaly": True,
                        "trial_id": f"{subject_id}_{act_name}_rep{rep+1}",
                        "timestamps_sec": t,
                        "accel": accel,
                        "gyro": gyro,
                    })

        return trials

    def generate_cohort(
        self,
        n_train_subjects: int = 14,
        n_val_subjects: int = 3,
        n_test_subjects: int = 4,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Generates an entire multi-subject cohort strictly partitioned by Subject ID.
        - Train Cohort: ONLY normal movement sequences from train subjects.
        - Val Cohort: ONLY normal movement sequences from unseen validation subjects.
        - Test Cohort: Normal + Anomalous sequences from holdout evaluation subjects.
        """
        train_trials: List[Dict[str, Any]] = []
        val_trials: List[Dict[str, Any]] = []
        test_trials: List[Dict[str, Any]] = []

        # 1. Train subjects (Normal only)
        for i in range(1, n_train_subjects + 1):
            sub_id = f"SUB_TR_{i:02d}"
            trials = self.generate_subject_session(sub_id, include_anomalies=False)
            train_trials.extend(trials)

        # 2. Val subjects (Normal only for validation baseline & early stopping)
        for i in range(1, n_val_subjects + 1):
            sub_id = f"SUB_VAL_{i:02d}"
            trials = self.generate_subject_session(sub_id, include_anomalies=False)
            val_trials.extend(trials)

        # 3. Test subjects (Normal + Abnormal for evaluation and threshold benchmarking)
        for i in range(1, n_test_subjects + 1):
            sub_id = f"SUB_TEST_{i:02d}"
            trials = self.generate_subject_session(sub_id, include_anomalies=True)
            test_trials.extend(trials)

        return train_trials, val_trials, test_trials
