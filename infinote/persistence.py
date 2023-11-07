import json
from pathlib import Path
from typing import List

from PySide6.QtWidgets import QGraphicsView


def load_scene(view: QGraphicsView, savedirs: List[Path]):
    loaded_any_folder = False
    filename_to_text = {}
    global_meta = {}
    for savedir in savedirs:
        # if there is at least one markdown file, open it
        # names must be integers
        meta_path = savedir / "meta.json"
        files = [f for f in savedir.iterdir() if f.suffix == ".md"]

        if files == [] or not meta_path.exists():
            print(f"no markdown files in {savedir}")
            # save some initial hue for this dir
            view.buf_handler.choose_hue_for_savedir(savedir)
            continue
        loaded_any_folder = True

        # load all

        meta = json.loads(meta_path.read_text())
        global_meta.update(meta)

        # load dir colors
        view.buf_handler.savedir_hues[savedir] = meta["hue"]

        # load files into buffers
        for full_filename in files:
            # TODO this may fail if savedir is passed as absolute
            filename = full_filename.as_posix()
            info = meta[filename]

            # create text
            text = view.buf_handler.open_filename(
                info["plane_pos"], info["manual_scale"], filename
            )
            filename_to_text[filename] = text

        # prepare the next file number
        max_filenum = max(int(f.stem) for f in files if f.stem.isnumeric())
        view.buf_handler.last_file_nums[savedir] = max_filenum

    # connect them
    for text in filename_to_text.values():
        info = global_meta[text.filename]
        text.child_down = filename_to_text.get(info["child_down"])
        text.child_right = filename_to_text.get(info["child_right"])
        text.parent = filename_to_text.get(info["parent"])

    assert loaded_any_folder, "no markdown files found in any folder"
    print(view.buf_handler.savedir_hues)


def save_scene(view: QGraphicsView, savedirs: List[Path]):
    # record text metadata
    metas = {savedir: {} for savedir in savedirs}
    for text in view.buf_handler.get_texts():
        if text.filename is None:
            # this buffer was not created by this program, so don't save it
            continue
        savedir = Path(text.filename).parent
        meta = metas[savedir]
        meta[text.filename] = dict(
            plane_pos=tuple(text.plane_pos.toTuple()),
            manual_scale=text.manual_scale,
            child_down=text.child_down.filename if text.child_down else None,
            child_right=text.child_right.filename if text.child_right else None,
            parent=text.parent.filename if text.parent else None,
        )

    # record other data
    for savedir, meta in metas.items():
        meta["hue"] = view.buf_handler.savedir_hues[savedir]

    # save metadata jsons
    for savedir, meta in metas.items():
        meta_path = savedir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=4))

    #########################################
    # save each text
    for text in view.buf_handler.get_texts():
        text.save(view.nvim)
