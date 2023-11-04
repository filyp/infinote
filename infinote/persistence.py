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
        files = [
            f for f in savedir.iterdir() if f.suffix == ".md" and f.stem.isnumeric()
        ]

        if files == [] or not meta_path.exists():
            print(f"no markdown files in {savedir}")
            continue
        loaded_any_folder = True

        # load all

        meta = json.loads(meta_path.read_text())
        global_meta.update(meta)

        # load them into buffers
        for full_filename in files:
            # get the full filename, but relative
            filename = full_filename.as_posix()
            info = meta[filename]
            # create text
            text = view.buf_handler.open_filename(
                info["plane_pos"], info["manual_scale"], filename
            )
            filename_to_text[filename] = text

        # prepare the next file number
        max_filenum = max(int(f.stem) for f in files)
        view.buf_handler.last_file_nums[savedir] = max_filenum

    # connect them
    for text in filename_to_text.values():
        info = global_meta[text.filename]
        text.child_down = filename_to_text.get(info["child_down"])
        text.child_right = filename_to_text.get(info["child_right"])
        text.parent = filename_to_text.get(info["parent"])

    assert loaded_any_folder, "no markdown files found in any folder"

    # set the global state
    main_meta_file = savedirs[0] / "meta.json"
    if main_meta_file.exists():
        main_meta = json.loads(main_meta_file.read_text())
        view.global_scale = main_meta["global_scale"]
        view.current_folder = (
            main_meta["current_folder"]
            if main_meta["current_folder"] in savedirs
            else savedirs[0]
        )


def save_scene(view: QGraphicsView, savedirs: List[Path]):
    # build metadata jsons
    metas = {}
    for savedir in savedirs:
        old_meta_file = savedir / "meta.json"
        if old_meta_file.exists():
            old_meta = json.loads((savedir / "meta.json").read_text())
            # take the old view metadata, but remove all the old text metadata
            metas[savedir] = {
                k: v for k, v in old_meta.items() if not k.endswith(".md")
            }
    # only save current view metadata to the main (first) savedir
    metas[savedirs[0]] = view.get_state()

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

    # save metadata jsons
    for savedir, meta in metas.items():
        meta_path = savedir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=4))

    #########################################
    # save each text
    for text in view.buf_handler.get_texts():
        text.save()
