"""
TourSafe LSTM Autoencoder Training Engine.
Handles PyTorch model training, learning rate scheduling, early stopping,
gradient norm clipping, and loss logging.
"""

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

from ..config import TrainingConfig
from ..models.lstm_autoencoder import TourSafeLSTMAutoencoder


@dataclass
class TrainingResult:
    best_model: TourSafeLSTMAutoencoder
    train_loss_history: List[float]
    val_loss_history: List[float]
    lr_history: List[float]
    best_epoch: int
    total_epochs: int
    best_val_loss: float
    training_duration_sec: float
    metrics_summary: Dict[str, Any] = field(default_factory=dict)


class AutoencoderTrainer:
    """
    Executes supervised reconstruction training on normal-motion IMU sequences.
    """

    def __init__(
        self,
        model: TourSafeLSTMAutoencoder,
        config: Optional[TrainingConfig] = None,
    ):
        self.model = model
        self.config = config or TrainingConfig()
        self.device = torch.device(self.config.device if torch.cuda.is_available() and self.config.device != "cpu" else "cpu")
        self.model.to(self.device)

        # Set random seeds for reproducibility
        torch.manual_seed(self.config.random_seed)
        np.random.seed(self.config.random_seed)

    def train(
        self,
        X_train_scaled: np.ndarray,
        X_val_scaled: np.ndarray,
        verbose: bool = True,
    ) -> TrainingResult:
        """
        Executes the complete training loop.

        Parameters
        ----------
        X_train_scaled : np.ndarray of shape (N_train, 150, 8)
        X_val_scaled : np.ndarray of shape (N_val, 150, 8)
        verbose : bool
        """
        start_time = time.time()

        # Build PyTorch DataLoaders
        t_train = torch.from_numpy(X_train_scaled.astype(np.float32))
        t_val = torch.from_numpy(X_val_scaled.astype(np.float32))

        train_ds = TensorDataset(t_train, t_train)  # Target is the input itself for autoencoder
        val_ds = TensorDataset(t_val, t_val)

        train_loader = DataLoader(
            train_ds,
            batch_size=self.config.batch_size,
            shuffle=True,
            drop_last=len(train_ds) > self.config.batch_size,
        )
        val_loader = DataLoader(
            val_ds,
            batch_size=self.config.batch_size,
            shuffle=False,
        )

        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=self.config.lr_reduce_factor,
            patience=self.config.lr_reduce_patience,
            min_lr=1e-6,
        )

        criterion = nn.MSELoss()

        train_loss_history: List[float] = []
        val_loss_history: List[float] = []
        lr_history: List[float] = []

        best_val_loss = float("inf")
        best_epoch = 0
        best_model_weights = copy.deepcopy(self.model.state_dict())
        epochs_no_improve = 0

        for epoch in range(1, self.config.epochs + 1):
            # --- Training Phase ---
            self.model.train()
            train_losses = []

            for batch_x, batch_target in train_loader:
                batch_x = batch_x.to(self.device)
                batch_target = batch_target.to(self.device)

                optimizer.zero_grad()
                reconstructed = self.model(batch_x)
                loss = criterion(reconstructed, batch_target)

                loss.backward()
                if self.config.clip_grad_norm > 0:
                    nn.utils.clip_grad_norm_(self.model.parameters(), self.config.clip_grad_norm)

                optimizer.step()
                train_losses.append(loss.item())

            avg_train_loss = float(np.mean(train_losses))
            train_loss_history.append(avg_train_loss)

            # --- Validation Phase ---
            self.model.eval()
            val_losses = []
            with torch.no_grad():
                for batch_x, batch_target in val_loader:
                    batch_x = batch_x.to(self.device)
                    batch_target = batch_target.to(self.device)

                    reconstructed = self.model(batch_x)
                    val_loss = criterion(reconstructed, batch_target)
                    val_losses.append(val_loss.item())

            avg_val_loss = float(np.mean(val_losses))
            val_loss_history.append(avg_val_loss)

            current_lr = optimizer.param_groups[0]["lr"]
            lr_history.append(current_lr)
            scheduler.step(avg_val_loss)

            # --- Early Stopping & Checkpointing ---
            if avg_val_loss < (best_val_loss - self.config.min_delta):
                best_val_loss = avg_val_loss
                best_epoch = epoch
                best_model_weights = copy.deepcopy(self.model.state_dict())
                epochs_no_improve = 0
            else:
                epochs_no_improve += 1

            if verbose and (epoch % 5 == 0 or epoch == 1 or epochs_no_improve >= self.config.early_stopping_patience):
                print(
                    f"Epoch [{epoch:03d}/{self.config.epochs:03d}] "
                    f"Train Loss: {avg_train_loss:.6f} | "
                    f"Val Loss: {avg_val_loss:.6f} (Best: {best_val_loss:.6f} @ Ep {best_epoch}) | "
                    f"LR: {current_lr:.2e}"
                )

            if epochs_no_improve >= self.config.early_stopping_patience:
                if verbose:
                    print(f"Early stopping triggered at epoch {epoch} (no improvement for {self.config.early_stopping_patience} epochs)")
                break

        # Load best weights
        self.model.load_state_dict(best_model_weights)
        duration = time.time() - start_time

        summary = {
            "best_epoch": best_epoch,
            "total_epochs_trained": len(train_loss_history),
            "best_val_loss": round(best_val_loss, 6),
            "final_train_loss": round(train_loss_history[-1], 6),
            "final_val_loss": round(val_loss_history[-1], 6),
            "training_duration_seconds": round(duration, 2),
            "converged": bool(best_val_loss < 0.1),
        }

        return TrainingResult(
            best_model=self.model,
            train_loss_history=train_loss_history,
            val_loss_history=val_loss_history,
            lr_history=lr_history,
            best_epoch=best_epoch,
            total_epochs=len(train_loss_history),
            best_val_loss=best_val_loss,
            training_duration_sec=duration,
            metrics_summary=summary,
        )
