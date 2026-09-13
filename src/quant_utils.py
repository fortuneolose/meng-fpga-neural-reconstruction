from copy import deepcopy

import torch
import torch.nn as nn


def quantize_weight_per_output_channel(weight, bits=8):
    """
    Symmetric signed per-output-channel weight quantisation.

    INT8 range:
        [-127, 127]

    Returns:
        qweight       actual integer tensor
        dequantized   simulated FP32 reconstruction of INT8 weights
        scales        one scale per output channel
    """

    qmax = (2 ** (bits - 1)) - 1
    qmin = -qmax

    weight = weight.detach()

    # Conv2d:
    # [out_channels, in_channels, kernel_h, kernel_w]
    reduce_dims = tuple(range(1, weight.ndim))

    max_abs = weight.abs().amax(
        dim=reduce_dims,
        keepdim=True
    )

    scales = max_abs / qmax

    # Protect against all-zero channels.
    scales = torch.where(
        scales == 0,
        torch.ones_like(scales),
        scales
    )

    qweight = torch.round(
        weight / scales
    )

    qweight = torch.clamp(
        qweight,
        qmin,
        qmax
    ).to(torch.int8)

    dequantized = (
        qweight.to(weight.dtype)
        * scales
    )

    channel_scales = scales.reshape(
        weight.shape[0]
    )

    return (
        qweight,
        dequantized,
        channel_scales
    )


def make_weight_quantized_model(fp32_model):
    """
    Copy an FP32 model and replace Conv2d weights
    with simulated INT8 -> dequantised weights.

    Activations remain FP32.
    Biases remain FP32.
    """

    quantized_model = deepcopy(fp32_model)

    packed = {}

    for name, module in quantized_model.named_modules():

        if isinstance(module, nn.Conv2d):

            qweight, dequantized, scales = (
                quantize_weight_per_output_channel(
                    module.weight,
                    bits=8
                )
            )

            module.weight.data.copy_(
                dequantized
            )

            packed[name] = {
                "qweight": qweight.cpu(),
                "scales": scales.cpu(),
                "bias": (
                    module.bias.detach().cpu().clone()
                    if module.bias is not None
                    else None
                ),
            }

    return quantized_model, packed

def fake_quantize_uint8(
    tensor,
    scale
):
    """
    Simulate unsigned 8-bit quantisation:
        q in [0, 255]

    Returns dequantised FP32 values so normal
    PyTorch operations can continue.
    """

    q = torch.round(
        tensor / scale
    )

    q = torch.clamp(
        q,
        0,
        255
    )

    return q * scale


def fake_quantize_int8(
    tensor,
    scale
):
    """
    Simulate symmetric signed 8-bit quantisation:
        q in [-127, 127]
    """

    q = torch.round(
        tensor / scale
    )

    q = torch.clamp(
        q,
        -127,
        127
    )

    return q * scale