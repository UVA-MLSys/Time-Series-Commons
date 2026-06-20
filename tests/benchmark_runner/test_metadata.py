import json
import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_registry():
    return json.loads((ROOT / "data/benchmark/model-registry.json").read_text())["models"]


def load_datasets():
    return json.loads((ROOT / "data/benchmark/dataset-metadata.json").read_text())["datasets"]


def test_paper1_all_purpose_models_are_registered_zero_shot_only():
    models = {m["model_id"]: m for m in load_registry()}

    for model_id in ["Chronos-2", "TTM-R3-FT", "Moirai2"]:
        assert model_id in models
        assert models[model_id]["model_type"] == "foundation"
        assert set(models[model_id]["io_modes"]) == {"UV-UV", "MV-UV", "MV-MV"}
        assert models[model_id]["evaluation_modes"] == ["zero_shot"]
        assert models[model_id]["source_link"].startswith("http")


def test_optional_models_are_labeled_by_supported_io_modes():
    models = {m["model_id"]: m for m in load_registry()}

    assert models["Toto-2"]["evaluation_modes"] == ["zero_shot"]
    assert set(models["Toto-2"]["io_modes"]) == {"UV-UV", "MV-MV"}
    assert "MV-UV" not in models["Toto-2"]["io_modes"]

    assert models["TimesFM-2.5"]["evaluation_modes"] == ["zero_shot"]
    assert set(models["TimesFM-2.5"]["io_modes"]) == {"UV-UV", "MV-UV"}
    assert "MV-MV" not in models["TimesFM-2.5"]["io_modes"]


def test_camels_us_is_registered_for_paper1_zero_shot():
    datasets = {d["dataset_id"]: d for d in load_datasets()}

    assert "camels-us" in datasets
    camels = datasets["camels-us"]
    assert camels["benchmark_ready"] is False
    assert set(camels["capabilities"]["io_modes"]) == {"UV-UV", "MV-UV", "MV-MV"}
    assert camels["capabilities"]["evaluation_modes"] == ["zero_shot"]


def test_paper1_huggingface_datasets_have_one_executable_registry_record_each():
    datasets = load_datasets()
    selected_ids = {
        "ett-hourly-station-1-etth1",
        "electricity-ecl",
        "traffic-dataset",
        "weather-dataset",
        "exchange",
        "m4-hourly",
        "m4-daily",
        "m4-monthly",
        "cdc_fluview_who_nrevss",
    }

    for dataset_id in selected_ids:
        matches = [dataset for dataset in datasets if dataset["dataset_id"] == dataset_id]
        assert len(matches) == 1, f"{dataset_id} has {len(matches)} registry records"
        dataset = matches[0]
        assert dataset["benchmark_id"]
        assert dataset["source"]["type"] == "huggingface"
        assert dataset["source"]["repo_id"] == "thuml/Time-Series-Library"
        assert len(dataset["source"]["revision"]) == 40
        assert dataset["source"]["revision"] != "main"
        assert dataset["source"]["url"].startswith("https://huggingface.co/")

        implementation = dataset["implementation"]
        module = importlib.import_module(implementation["module"])
        assert getattr(module, implementation["class"])
