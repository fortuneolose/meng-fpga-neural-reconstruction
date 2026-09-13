import torch
import torch.nn as nn
import torch.nn.functional as F


class ResidualReconstructionCNN(nn.Module):
    def __init__(self):
        super().__init__()

        self.conv1 = nn.Conv2d(
            in_channels=1,
            out_channels=8,
            kernel_size=3,
            padding=1
        )

        self.conv2 = nn.Conv2d(
            in_channels=8,
            out_channels=8,
            kernel_size=3,
            padding=1
        )

        self.conv3 = nn.Conv2d(
            in_channels=8,
            out_channels=1,
            kernel_size=3,
            padding=1
        )

        # Start with zero residual correction.
        # Initial output therefore equals the bilinear baseline.
        nn.init.zeros_(self.conv3.weight)
        nn.init.zeros_(self.conv3.bias)

    def forward(self, x):

        # 128x128 -> 256x256 conventional reconstruction
        baseline = F.interpolate(
            x,
            scale_factor=2,
            mode="bilinear",
            align_corners=False
        )

        # Predict only the correction to the baseline
        residual = F.relu(self.conv1(baseline))
        residual = F.relu(self.conv2(residual))
        residual = self.conv3(residual)

        output = baseline + residual

        return output