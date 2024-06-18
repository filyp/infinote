import json
from pathlib import Path

from colormath.color_conversions import convert_color
from colormath.color_objects import HSLColor, LCHabColor
from pynvim import Nvim

from infinote.buffer_handling import BufferHandler
from infinote.config import Config
from infinote.text_object import BoxInfo


def _name_to_hue(name: str):
    # choose the hue in a perceptually uniform way
    # choose a num between 60 and 310 degrees, to avoid non-persistent's red
    uniform = (name.__hash__() % 250) + 60  # note: this hash is changing
    random_lch_color = LCHabColor(100, 128, uniform)
    random_HSL_color = convert_color(random_lch_color, HSLColor)
    hue = int(random_HSL_color.hsl_h)
    return hue


def load_scene(buf_handler: BufferHandler, group_dir: Path):
    filename_to_text = {}
    top_dir = group_dir.parent
    top_dir.mkdir(parents=True, exist_ok=True)
    meta = {}

    if not group_dir.exists():
        # save some initial hue for this dir
        hue = _name_to_hue(group_dir.stem)
        meta[group_dir.name] = dict(hue=hue)
        buf_handler.savedir_hues[group_dir] = hue

    meta_path = top_dir / "meta.json"
    if not meta_path.exists():
        print(f"opening a new workspace in {top_dir}")
        # if there is no meta, top_dir should be empty
        assert not any(top_dir.iterdir()), f"workdir_dir not empty: {top_dir}"
        # create the main subdir
        group_dir.mkdir(exist_ok=True)
        # create one text
        buf_handler.create_text(group_dir, BoxInfo())
        return

    # create the main subdir
    group_dir.mkdir(exist_ok=True)
    meta.update(json.loads(meta_path.read_text()))
    subdirs = [d for d in top_dir.iterdir() if d.is_dir()]
    print(f"subdirs: {[dir.name for dir in subdirs]}")
    for subdir in subdirs:
        # load dir color
        assert subdir.name in meta, f"alien folder: {subdir}"
        buf_handler.savedir_hues[subdir] = meta[subdir.name]["hue"]

        # load files into buffers
        files = [f for f in subdir.iterdir() if f.suffix == ".md"]
        for full_filename in files:
            rel_filename = full_filename.relative_to(top_dir).as_posix()
            assert full_filename.stem.isnumeric(), f"names must be integers: {rel_filename}"
            assert rel_filename in meta, f"alien file: {rel_filename}"
            box_info = BoxInfo(**meta[rel_filename])

            if meta.get("active_text") and rel_filename == meta["active_text"]:
                last_box_info = box_info
                last_filename = full_filename
                continue

            # create text
            text = buf_handler.open_filename(box_info, full_filename.as_posix())
            filename_to_text[rel_filename] = text

        # prepare the next file number
        max_filenum = max(int(f.stem) for f in files) if files else 0
        buf_handler.last_file_nums[subdir] = max_filenum

    # load the last active text
    if meta.get("active_text"):
        text = buf_handler.open_filename(last_box_info, last_filename.as_posix())
        rel_filename = last_filename.relative_to(top_dir).as_posix()
        filename_to_text[rel_filename] = text

    # connect them
    for rel_filename, text in filename_to_text.items():
        box_info = meta[rel_filename]
        buf_handler.parents[text] = filename_to_text.get(box_info["parent_filename"])

    print(f"loaded {len(filename_to_text)} texts")


def save_scene(buf_handler: BufferHandler, nvim: Nvim, group_dir: Path):
    workspace_dir = group_dir.parent
    # record text metadata
    meta = {}


    for text in buf_handler.get_texts():
        if text.filename is None:
            # this buffer was not created by this program, so don't save it
            continue
        rel_filename = Path(text.filename).relative_to(workspace_dir).as_posix()
        meta[rel_filename] = dict(
            plane_pos=tuple(text.plane_pos.toTuple()),
            manual_scale=text.manual_scale,
            scale_rel_to_parent=text.scale_rel_to_parent,
            pos_rel_to_parent=(
                tuple(text.pos_rel_to_parent.toTuple()) if text.pos_rel_to_parent else None
            ),
            parent_filename=text.parent_filename,
        )

    # record other data
    for subdir, hue in buf_handler.savedir_hues.items():
        meta[subdir.name] = dict(hue=hue)

    meta["active_text"] = buf_handler.get_current_text().get_rel_filename()

    # save metadata json
    meta_path = workspace_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=4))

    #########################################
    # save each text
    for text in buf_handler.get_texts():
        text.save(nvim)
