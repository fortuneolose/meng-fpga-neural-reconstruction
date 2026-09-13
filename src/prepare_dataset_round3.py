from pathlib import Path

from PIL import Image


TRAIN_SOURCE = Path("data/round3/train_source")
VAL_SOURCE = Path("data/round3/val_source")

TRAIN_HR = Path("data/round3/train/hr")
TRAIN_LR = Path("data/round3/train/lr")

VAL_HR = Path("data/round3/val/hr")
VAL_LR = Path("data/round3/val/lr")

PATCH_SIZE = 256
LR_SIZE = 128


def ensure_dirs():
    for path in [
        TRAIN_HR,
        TRAIN_LR,
        VAL_HR,
        VAL_LR,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def grayscale(image):
    return image.convert("L")


def crop_positions(width, height):
    """
    Five deterministic 256x256 crops:
    top-left, top-right, bottom-left,
    bottom-right and centre.
    """
    p = PATCH_SIZE

    return [
        (0, 0),
        (width - p, 0),
        (0, height - p),
        (width - p, height - p),
        ((width - p) // 2, (height - p) // 2),
    ]


def save_pair(patch, stem, hr_dir, lr_dir):

    hr_path = hr_dir / f"{stem}_hr.png"
    lr_path = lr_dir / f"{stem}_lr.png"

    patch.save(hr_path)

    low_res = patch.resize(
        (LR_SIZE, LR_SIZE),
        Image.Resampling.BICUBIC
    )

    low_res.save(lr_path)


def prepare_training():

    count = 0

    for source_path in sorted(
        TRAIN_SOURCE.glob("*.jpeg")
    ):

        image = grayscale(
            Image.open(source_path)
        )

        width, height = image.size

        if (
            width < PATCH_SIZE
            or height < PATCH_SIZE
        ):
            print(
                f"Skipping {source_path.name}: "
                "image too small"
            )
            continue

        for index, (x, y) in enumerate(
            crop_positions(width, height)
        ):

            patch = image.crop(
                (
                    x,
                    y,
                    x + PATCH_SIZE,
                    y + PATCH_SIZE,
                )
            )

            stem = (
                f"{source_path.stem}"
                f"_p{index:02d}"
            )

            save_pair(
                patch,
                stem,
                TRAIN_HR,
                TRAIN_LR,
            )

            count += 1

    print(
        f"Training pairs created: {count}"
    )


def prepare_validation():

    count = 0

    for source_path in sorted(
        VAL_SOURCE.glob("*.jpeg")
    ):

        image = grayscale(
            Image.open(source_path)
        )

        width, height = image.size

        if (
            width < PATCH_SIZE
            or height < PATCH_SIZE
        ):
            print(
                f"Skipping {source_path.name}: "
                "image too small"
            )
            continue

        # One deterministic centre crop only.
        x = (width - PATCH_SIZE) // 2
        y = (height - PATCH_SIZE) // 2

        patch = image.crop(
            (
                x,
                y,
                x + PATCH_SIZE,
                y + PATCH_SIZE,
            )
        )

        save_pair(
            patch,
            source_path.stem,
            VAL_HR,
            VAL_LR,
        )

        count += 1

    print(
        f"Validation pairs created: {count}"
    )


def inspect_dataset():

    train_hr = sorted(
        TRAIN_HR.glob("*.png")
    )

    train_lr = sorted(
        TRAIN_LR.glob("*.png")
    )

    val_hr = sorted(
        VAL_HR.glob("*.png")
    )

    val_lr = sorted(
        VAL_LR.glob("*.png")
    )

    print()
    print("Round 3 dataset summary")
    print("-----------------------")

    print(
        f"Training HR patches:   "
        f"{len(train_hr)}"
    )

    print(
        f"Training LR patches:   "
        f"{len(train_lr)}"
    )

    print(
        f"Validation HR patches: "
        f"{len(val_hr)}"
    )

    print(
        f"Validation LR patches: "
        f"{len(val_lr)}"
    )

    if train_hr and train_lr:

        hr = Image.open(train_hr[0])
        lr = Image.open(train_lr[0])

        print()
        print("Example pair")
        print(f"HR size: {hr.size}")
        print(f"LR size: {lr.size}")
        print(f"HR mode: {hr.mode}")
        print(f"LR mode: {lr.mode}")


if __name__ == "__main__":

    ensure_dirs()

    prepare_training()

    prepare_validation()

    inspect_dataset()