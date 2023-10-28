import json
from pathlib import Path

from PySide6.QtWidgets import QGraphicsView


def load_scene(view: QGraphicsView, savedir: Path):
    # if there is at least one markdown file, open it
    # names must be integers
    meta_path = savedir / "meta.json"
    files = [f for f in savedir.iterdir() if f.suffix == ".md" and f.stem.isnumeric()]

    assert files != [] and meta_path.exists(), "No files to load"

    # load all

    meta = json.loads(meta_path.read_text())
    view.global_scale = meta["global_scale"]

    # load them into buffers
    for filename in files:
        full_text = filename.read_text()
        index = int(filename.stem)
        text_info = meta[str(index)]
        # create text
        view.open_filenum(text_info["plane_pos"], text_info["manual_scale"], index)

    # prepare the next file number
    max_filenum = max(int(f.stem) for f in files)
    view.last_file_num = max_filenum


def save_scene(view: QGraphicsView, savedir: Path):
    # save
    # # backpup the dir to .[name]_backup
    # backup = savedir.parent / f".{savedir.name}_backup"
    # # if backup exists, delete it
    # if backup.exists():
    #     for f in backup.iterdir():
    #         f.unlink()
    #     backup.rmdir()
    # # move the savedir to backup
    # savedir.rename(backup)
    # # create a new savedir
    # new_savedir = Path(sys.argv[1])
    # new_savedir.mkdir(parents=True, exist_ok=True)

    # save each text
    for text in view.get_texts():
        text.save()

    # save metadata json
    meta = dict(global_scale=view.global_scale)
    for text in view.get_texts():
        if text.filenum < 0:
            # this buffer was not created by this program, so don't save it
            continue
        meta[text.filenum] = dict(
            plane_pos=tuple(text.plane_pos.toTuple()),
            manual_scale=text.manual_scale,
        )
    meta_path = Path("meta.json")
    meta_path.write_text(json.dumps(meta, indent=4))
