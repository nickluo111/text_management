"""The full-corpus storage selection must also work through the normal CLI."""
import json

import pytest

from yelptext.cli.main import main
from tests.test_search_engine import cli_config


def compact_config(tmp_path):
    config, prepared, index_dir = cli_config(tmp_path)
    config.write_text(
        config.read_text(encoding="utf-8").replace("[index]\n", '[index]\nstorage="compact"\n'),
        encoding="utf-8",
    )
    return config, prepared, index_dir


def test_compact_cli_build_and_query(tmp_path, capsys):
    config, _, index_dir = compact_config(tmp_path)
    main(["index", "build", "--config", str(config)])
    built = json.loads(capsys.readouterr().out)
    assert built["stats"]["backend"] == "compact-v1"
    assert built["index_path"].endswith("compact.sqlite3")
    for ranker in ("tfidf", "bm25"):
        main(["search", "apple banana", "--ranker", ranker, "--config", str(config)])
        results = json.loads(capsys.readouterr().out)["results"]
        assert [hit["doc_id"] for hit in results] == ["d1", "d2", "d3"]
    assert (index_dir / "norms.npy").is_file()


@pytest.mark.parametrize("filename", ["compact.sqlite3", "manifest.json", "lengths.npy", "norms.npy"])
def test_compact_cli_preserves_every_index_file(tmp_path, capsys, filename):
    config, _, index_dir = compact_config(tmp_path)
    main(["index", "build", "--config", str(config)])
    capsys.readouterr()
    output = index_dir / filename
    before = output.read_bytes()
    with pytest.raises(ValueError, match="overwrite"):
        main(["search", "apple", "--config", str(config), "--output", str(output)])
    assert output.read_bytes() == before


def test_unknown_storage_is_not_silently_ignored(tmp_path):
    config, _, index_dir = compact_config(tmp_path)
    config.write_text(config.read_text(encoding="utf-8").replace('storage="compact"', 'storage="invalid"'), encoding="utf-8")
    with pytest.raises(ValueError, match="storage"):
        main(["index", "build", "--config", str(config)])
    assert not index_dir.exists()

