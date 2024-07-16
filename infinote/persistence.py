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


def get_box_info(full_filename: Path):
    info_path = full_filename.parent / "boxinfo" / f"{full_filename.stem}.json"  # NOSONAR
    info = json.loads(info_path.read_text())
    return BoxInfo(**info)


def load_scene(buf_handler: BufferHandler, group_dir: Path):
    workspace_dir = group_dir.parent
    workspace_dir.mkdir(parents=True, exist_ok=True)
    meta = {}

    if not group_dir.exists():
        # save some initial hue for this dir
        hue = _name_to_hue(group_dir.stem)
        meta[group_dir.name] = dict(hue=hue)
        buf_handler.savedir_hues[group_dir] = hue

    meta_path = workspace_dir / "meta.json"
    if not meta_path.exists():
        print(f"opening a new workspace in {workspace_dir}")
        # if there is no meta, top_dir should be empty
        assert not any(workspace_dir.iterdir()), f"workspace_dir not empty: {workspace_dir}"
        # create the main subdir
        group_dir.mkdir(exist_ok=True)
        (group_dir / "boxinfo").mkdir(exist_ok=True)
        # create one text
        buf_handler.create_text(group_dir, BoxInfo())
        return

    # create the main subdir
    group_dir.mkdir(exist_ok=True)
    (group_dir / "boxinfo").mkdir(exist_ok=True)
    meta.update(json.loads(meta_path.read_text()))
    subdirs = [d for d in workspace_dir.iterdir() if d.is_dir()]
    print(f"subdirs: {[dir.name for dir in subdirs]}")
    filename_to_text = {}
    for subdir in subdirs:
        # load dir color
        assert subdir.name in meta, f"alien folder: {subdir}"
        buf_handler.savedir_hues[subdir] = meta[subdir.name]["hue"]

        # load files into buffers
        files = [f for f in subdir.iterdir() if f.suffix in [".md", ".aichat"]]
        for full_filename in files:
            rel_filename = full_filename.relative_to(workspace_dir).as_posix()
            assert full_filename.stem.isnumeric(), f"names must be integers: {rel_filename}"
            box_info = get_box_info(full_filename)

            # create text
            text = buf_handler.open_filename(box_info, full_filename.as_posix())
            filename_to_text[full_filename] = text

        # prepare the next file number
        max_filenum = max(int(f.stem) for f in files) if files else 0
        buf_handler.last_file_nums[subdir] = max_filenum

    # select the last active text
    last_active_text = meta.get("active_text")
    if last_active_text is not None:
        buf_handler.jump_to_file(last_active_text)

    # connect them
    for full_filename, text in filename_to_text.items():
        box_info = get_box_info(full_filename)
        if box_info.parent_filename:
            parent_full_filename = workspace_dir / box_info.parent_filename
            buf_handler.parents[text] = filename_to_text.get(parent_full_filename)

    print(f"loaded {len(filename_to_text)} texts")


def save_scene(buf_handler: BufferHandler, nvim: Nvim, workspace_dir: Path):
    # save metadata json
    meta = {}
    for subdir, hue in buf_handler.savedir_hues.items():
        meta[subdir.name] = dict(hue=hue)
    meta["active_text"] = buf_handler.get_current_text().get_rel_filename()
    meta_path = workspace_dir / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=4))

    # save each text
    for text in buf_handler.get_texts():
        if text.filename is None:
            # this buffer was not created by this program, so don't save it
            continue
        text.persist_info()
        text.save_text_buffer(nvim)
