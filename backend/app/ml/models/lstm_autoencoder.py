"""
TourSafe PyTorch LSTM Autoencoder Architecture.
Learns deep temporal representations of normal human locomotion and computes
reconstruction error as a continuous anomaly metric.
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import torch
import torch.nn as nn

from ..config import ModelConfig


class LSTMEncoder(nn.Module):
    """
    Encodes an input sequence of shape (B, T, D) into a compressed latent bottleneck vector (B, L).
    """

    def __init__(
        self,
        input_dim: int = 8,
        hidden_dims: Optional[List[int]] = None,
        latent_dim: int = 16,
        dropout: float = 0.2,
    ):
        super().__init__()
        hidden_dims = hidden_dims or [64, 32]
        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.latent_dim = latent_dim

        # Layer 1: Input -> Hidden 0 (e.g. 8 -> 64)
        self.lstm1 = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dims[0],
            batch_first=True,
        )
        self.dropout1 = nn.Dropout(dropout)

        # Layer 2: Hidden 0 -> Hidden 1 (e.g. 64 -> 32)
        self.lstm2 = nn.LSTM(
            input_size=hidden_dims[0],
            hidden_size=hidden_dims[1],
            batch_first=True,
        )
        self.dropout2 = nn.Dropout(dropout)

        # Bottleneck projection: Hidden 1 last state -> Latent vector
        self.fc_latent = nn.Linear(hidden_dims[1], latent_dim)
        self.act_latent = nn.LeakyReLU(0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, T, input_dim)
        out, _ = self.lstm1(x)
        out = self.dropout1(out)
        out, (h_n, _) = self.lstm2(out)
        # Use final hidden state from top LSTM layer: h_n[-1] has shape (B, hidden_dims[1])
        latent = self.act_latent(self.fc_latent(h_n[-1]))
        return latent  # (B, latent_dim)


class LSTMDecoder(nn.Module):
    """
    Decodes the latent bottleneck vector (B, L) back into the reconstructed sequence (B, T, D).
    """

    def __init__(
        self,
        output_dim: int = 8,
        sequence_length: int = 150,
        hidden_dims: Optional[List[int]] = None,
        latent_dim: int = 16,
        dropout: float = 0.2,
    ):
        super().__init__()
        hidden_dims = hidden_dims or [32, 64]
        self.output_dim = output_dim
        self.sequence_length = sequence_length
        self.hidden_dims = hidden_dims
        self.latent_dim = latent_dim

        # Layer 1: Latent -> Hidden 0 (e.g. 16 -> 32)
        self.lstm1 = nn.LSTM(
            input_size=latent_dim,
            hidden_size=hidden_dims[0],
            batch_first=True,
        )
        self.dropout1 = nn.Dropout(dropout)

        # Layer 2: Hidden 0 -> Hidden 1 (e.g. 32 -> 64)
        self.lstm2 = nn.LSTM(
            input_size=hidden_dims[0],
            hidden_size=hidden_dims[1],
            batch_first=True,
        )
        self.dropout2 = nn.Dropout(dropout)

        # TimeDistributed Output Projection: Hidden 1 -> Output Dim (e.g. 64 -> 8)
        self.fc_out = nn.Linear(hidden_dims[1], output_dim)

    def forward(self, z: torch.Tensor) -> torch.Tensor:
        # z: (B, latent_dim)
        # Repeat latent vector across all T timesteps: (B, T, latent_dim)
        z_repeated = z.unsqueeze(1).repeat(1, self.sequence_length, 1)

        out, _ = self.lstm1(z_repeated)
        out = self.dropout1(out)
        out, _ = self.lstm2(out)
        out = self.dropout2(out)

        # Reconstructed sequence (B, T, output_dim)
        x_recon = self.fc_out(out)
        return x_recon


class TourSafeLSTMAutoencoder(nn.Module):
    """
    Complete LSTM Autoencoder for TourSafe IMU Anomaly Detection.
    """

    def __init__(self, config: Optional[ModelConfig] = None):
        super().__init__()
        self.config = config or ModelConfig()

        enc_hidden = self.config.hidden_dims
        dec_hidden = list(reversed(enc_hidden))

        self.encoder = LSTMEncoder(
            input_dim=self.config.input_dim,
            hidden_dims=enc_hidden,
            latent_dim=self.config.latent_dim,
            dropout=self.config.dropout,
        )

        self.decoder = LSTMDecoder(
            output_dim=self.config.input_dim,
            sequence_length=self.config.sequence_length,
            hidden_dims=dec_hidden,
            latent_dim=self.config.latent_dim,
            dropout=self.config.dropout,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        End-to-end forward pass: x -> latent -> x_recon.
        Input: (B, T, D), Output: (B, T, D)
        """
        z = self.encoder(x)
        x_recon = self.decoder(z)
        return x_recon

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        return self.encoder(x)

    def compute_reconstruction_error(
        self,
        x: torch.Tensor,
        error_type: str = "mse",
    ) -> torch.Tensor:
        """
        Computes per-window scalar reconstruction error (anomaly score).

        Parameters
        ----------
        x : torch.Tensor of shape (B, T, D)
        error_type : str ('mse' or 'mae')

        Returns
        -------
        scores : torch.Tensor of shape (B,)
        """
        x_recon = self.forward(x)
        diff = x - x_recon

        if error_type == "mae":
            # Mean absolute error over (T, D)
            return torch.mean(torch.abs(diff), dim=(1, 2))
        else:
            # Mean squared error over (T, D)
            return torch.mean(torch.square(diff), dim=(1, 2))

    def compute_per_timestep_error(self, x: torch.Tensor) -> torch.Tensor:
        """
        Computes error per timestep across channels: (B, T).
        Useful for temporal anomaly localization.
        """
        x_recon = self.forward(x)
        diff = x - x_recon
        return torch.mean(torch.square(diff), dim=2)

    def export_onnx(
        self,
        file_path: Union[str, Path],
        batch_size: int = 1,
        device: str = "cpu",
    ) -> Path:
        """
        Exports model to standardized ONNX graph with dynamic batch dimension.
        """
        out_p = Path(file_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        self.eval()
        self.to(device)

        dummy_input = torch.randn(
            batch_size,
            self.config.sequence_length,
            self.config.input_dim,
            dtype=torch.float32,
            device=device,
        )

        torch.onnx.export(
            self,
            dummy_input,
            str(out_p),
            export_params=True,
            opset_version=14,
            do_constant_folding=True,
            dynamo=False,
            input_names=["imu_window"],
            output_names=["reconstructed_window"],
            dynamic_axes={
                "imu_window": {0: "batch_size"},
                "reconstructed_window": {0: "batch_size"},
            },
        )
        return out_p
