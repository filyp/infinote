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

    filenum_to_text = {}

    # load them into buffers
    for filename in files:
        filenum = int(filename.stem)
        info = meta[str(filenum)]
        # create text
        text = view.buf_handler.open_filenum(
            info["plane_pos"], info["manual_scale"], filenum
        )
        filenum_to_text[filenum] = text

    # connect them
    for text in filenum_to_text.values():
        info = meta[str(text.filenum)]
        # note that some filenum pointers can be -1, but they will be ignored
        text.child_down = filenum_to_text.get(info["child_down"])
        text.child_right = filenum_to_text.get(info["child_right"])
        text.parent = filenum_to_text.get(info["parent"])

    # prepare the next file number
    max_filenum = max(int(f.stem) for f in files)
    view.buf_handler.last_file_num = max_filenum


def save_scene(view: QGraphicsView, savedir: Path):
    # save each text
    for text in view.buf_handler.get_texts():
        text.save()

    # save metadata json
    meta = dict(global_scale=view.global_scale)
    for text in view.buf_handler.get_texts():
        if text.filenum < 0:
            # this buffer was not created by this program, so don't save it
            continue
        meta[text.filenum] = dict(
            plane_pos=tuple(text.plane_pos.toTuple()),
            manual_scale=text.manual_scale,
            child_down=text.child_down.filenum if text.child_down else None,
            child_right=text.child_right.filenum if text.child_right else None,
            parent=text.parent.filenum if text.parent else None,
        )
    meta_path = Path("meta.json")
    meta_path.write_text(json.dumps(meta, indent=4))
