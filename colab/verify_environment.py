from __future__ import annotations

import argparse
from importlib import metadata
import platform


PACKAGE_NAMES = {
    "chronos": ("chronos-forecasting", "gluonts"),
    "moirai": ("uni2ts", "gluonts"),
    "timesfm25": ("timesfm", "gluonts"),
    "toto2": ("toto-2", "gluonts"),
    "flowstate": ("granite-tsfm", "gluonts"),
    "patchtst": ("granite-tsfm", "gluonts"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a Colab model environment.")
    parser.add_argument("--env", required=True, choices=sorted(PACKAGE_NAMES))
    args = parser.parse_args()

    import pandas
    import pyarrow
    import requests
    import torch
    from gluonts.dataset.split import split  # noqa: F401

    if args.env == "chronos":
        from chronos import Chronos2Pipeline  # noqa: F401
    elif args.env in {"flowstate", "patchtst"}:
        from tsfm_public import TimeSeriesForecastingPipeline  # noqa: F401
        from tsfm_public.toolkit.get_model import get_model  # noqa: F401
    elif args.env == "moirai":
        from uni2ts.model.moirai2 import Moirai2Forecast, Moirai2Module  # noqa: F401
    elif args.env == "timesfm25":
        import timesfm

        if not hasattr(timesfm, "ForecastConfig") or not hasattr(timesfm, "TimesFM_2p5_200M_torch"):
            from timesfm import configs  # noqa: F401
            from timesfm.timesfm_2p5 import timesfm_2p5_torch  # noqa: F401
    elif args.env == "toto2":
        from toto2 import Toto2Model  # noqa: F401

    versions = {
        "python": platform.python_version(),
        "pandas": pandas.__version__,
        "pyarrow": pyarrow.__version__,
        "requests": requests.__version__,
        "torch": torch.__version__,
    }
    for package_name in PACKAGE_NAMES[args.env]:
        versions[package_name] = metadata.version(package_name)

    cuda_available = torch.cuda.is_available()
    print(f"environment={args.env}")
    for name, version in versions.items():
        print(f"{name}={version}")
    print(f"cuda_available={cuda_available}")
    if cuda_available:
        print(f"cuda_device={torch.cuda.get_device_name(0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
