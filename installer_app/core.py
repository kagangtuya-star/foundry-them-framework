from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

WORLD_PATTERN = re.compile(r"(const WORLD_JOIN_THEMES = Object\.freeze\()\s*\{([\s\S]*?)\}(\s*\);)", re.MULTILINE)
SCRIPT_PATTERN = re.compile(r"(const JOIN_THEME_SCRIPTS = Object\.freeze\()\s*\{([\s\S]*?)\}(\s*\);)", re.MULTILINE)
JOIN_VIEW_PATTERN = re.compile(r"(^\s*(?:async\s+)?#joinView\(\)\s*\{[\s\S]*?^\s*\})", re.MULTILINE)

JOIN_VIEW_BLOCK = """
  async #joinView() {
    if ( !globalThis.SIGNED_EULA ) window.location.href = foundry.utils.getRoute("license");

    this.users = new foundry.documents.collections.Users(this.data.users);
    this.collections.set("User", this.users);

    foundry.documents.collections.Users._activateSocketListeners(this.socket);

    let JoinFormClass = JoinGameForm;
    const themeKey = this.world?.joinTheme;
    if ( themeKey ) console.info(`Join theme loader: detected theme ${themeKey}`);

    if ( themeKey && (themeKey !== "default") && (themeKey !== "minimal") ) {
      const scriptPath = JOIN_THEME_SCRIPTS?.[themeKey];
      if ( scriptPath ) {
        try {
          console.info(`Join theme loader: attempting to fetch ${themeKey} from ${scriptPath}`);
          const response = await fetch(scriptPath);
          if ( response.ok ) {
            const source = await response.text();
            const themeFactory = Function("return " + source);
            const CustomJoinForm = themeFactory();
            if ( typeof CustomJoinForm === "function" ) {
              JoinFormClass = CustomJoinForm;
              console.info(`Join theme loader: loaded theme ${themeKey}`);
            }
            else {
              console.warn(`Join theme loader: script ${scriptPath} did not export a class.`);
            }
          }
          else {
            console.warn(`Join theme script ${scriptPath} returned ${response.status}`);
          }
        }
        catch (err) {
          console.error(`Failed to load join theme script ${scriptPath}`, err);
        }
      }
    }

    ui.join = new JoinFormClass();
    ui.join.render({force: true});
  }
""".strip("\n")

CONFIG_PATH = Path(__file__).parent / "config.json"
MARKER_NAME = ".join-theme-framework.json"


def load_tool_config() -> Dict[str, str]:
    default = {
        "version": "1.0.0",
        "default_themes": ["simple"],
        "last_update": datetime.utcnow().isoformat() + "Z",
        "recent_roots": []
    }
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8")
    return default


def save_tool_config(config: Dict[str, str]):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def load_mapping(block: str) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for line in block.splitlines():
        entry = line.strip().rstrip(",")
        if not entry or ":" not in entry:
            continue
        key, value = entry.split(":", 1)
        mapping[key.strip().strip("'\"")] = value.strip().strip("'\"")
    return mapping


def dump_mapping(mapping: Dict[str, str]) -> str:
    if not mapping:
        return "{}"
    inner = ",\n".join(f'  {k}: "{v}"' for k, v in mapping.items())
    return "{\n" + inner + "\n}"


def backup(path: Path):
    if not path.exists():
        return
    backup_path = path.with_suffix(path.suffix + ".backup")
    if backup_path.exists():
        return
    shutil.copy2(path, backup_path)


def patch_block(content: str, pattern: re.Pattern, entries: Dict[str, str]) -> str:
    match = pattern.search(content)
    if not match:
        raise RuntimeError("未找到目标代码块，可能不支持该版本。")
    current = load_mapping(match.group(2))
    current.update(entries)
    block = dump_mapping(current)
    return content[:match.start(2)] + block[1:-1] + content[match.end(2):]


def insert_script_map(content: str, entries: Dict[str, str]) -> str:
    match = SCRIPT_PATTERN.search(content)
    if match:
        return patch_block(content, SCRIPT_PATTERN, entries)
    world_match = WORLD_PATTERN.search(content)
    if not world_match:
        raise RuntimeError("无法注入 JOIN_THEME_SCRIPTS。")
    block = dump_mapping(entries)
    insert = f"\nconst JOIN_THEME_SCRIPTS = Object.freeze({block});\n"
    return content[:world_match.end()] + insert + content[world_match.end():]


def patch_join_view(content: str) -> str:
    if "Join theme loader" in content:
        return content
    match = JOIN_VIEW_PATTERN.search(content)
    if not match:
        raise RuntimeError("未找到 #joinView 定义，无法自动补丁。")
    return content[:match.start()] + JOIN_VIEW_BLOCK + content[match.end():]


def validate_theme_id(theme_id: str) -> str:
    if re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", theme_id):
        return theme_id
    safe = re.sub(r"[^A-Za-z0-9_]", "_", theme_id)
    if not safe or not (safe[0].isalpha() or safe[0] == "_"):
        safe = f"theme_{safe}"
    return safe


def apply_patches(root: Path, theme_labels: Dict[str, str], script_map: Dict[str, str]):
    foundry_path = root / "public/scripts/foundry.mjs"
    constants_path = root / "common/constants.mjs"
    if not foundry_path.exists() or not constants_path.exists():
        raise RuntimeError("未找到 foundry.mjs 或 constants.mjs。")

    backup(foundry_path)
    backup(constants_path)

    foundry_data = foundry_path.read_text(encoding="utf-8")
    constants_data = constants_path.read_text(encoding="utf-8")

    sanitized_labels = {validate_theme_id(k): v for k, v in theme_labels.items()}
    sanitized_scripts = {validate_theme_id(k): v for k, v in script_map.items()}

    foundry_data = patch_block(foundry_data, WORLD_PATTERN, sanitized_labels)
    foundry_data = insert_script_map(foundry_data, sanitized_scripts)
    foundry_data = patch_join_view(foundry_data)
    constants_data = patch_block(constants_data, WORLD_PATTERN, sanitized_labels)

    foundry_path.write_text(foundry_data, encoding="utf-8")
    constants_path.write_text(constants_data, encoding="utf-8")
    write_marker(root, load_tool_config())


def restore_backups(root: Path):
    for rel in ("public/scripts/foundry.mjs", "common/constants.mjs"):
        path = root / rel
        backup_path = path.with_suffix(path.suffix + ".backup")
        if backup_path.exists():
            shutil.copy2(backup_path, path)
    marker = root / MARKER_NAME
    if marker.exists():
        marker.unlink()


def copy_resources(root: Path, resource_root: Path, entries: Iterable[str]):
    for rel in entries:
        src = resource_root / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def ensure_simple_theme(root: Path, resource_root: Path):
    assets = [
        "templates/joinmenu-so-nice/simple/simple-hero.hbs",
        "templates/joinmenu-so-nice/simple/simple-form.hbs",
        "templates/joinmenu-so-nice/simple/simple-setup.hbs",
        "public/joinmenu-so-nice/simple/custom.css",
        "public/joinmenu-so-nice/simple/joinmenu.js",
    ]
    copy_resources(root, resource_root, assets)


def set_theme_background_video(root: Path, theme_id: str, source_video: Path) -> Path:
    if not source_video.exists():
        raise FileNotFoundError("所选视频文件不存在。")
    if source_video.suffix.lower() != ".webm":
        raise ValueError("仅支持 WebM 视频。")
    dest_dir = root / "public/joinmenu-so-nice" / theme_id
    if not dest_dir.exists():
        raise RuntimeError("未找到该主题的 public 目录。请先安装该主题。")
    dest_path = dest_dir / "background.webm"
    shutil.copy2(source_video, dest_path)
    return dest_path


def discover_themes(root: Path) -> Dict[str, str]:
    foundry_path = root / "public/scripts/foundry.mjs"
    if not foundry_path.exists():
        return {}
    content = foundry_path.read_text(encoding="utf-8")
    match = WORLD_PATTERN.search(content)
    if not match:
        return {}
    return load_mapping(match.group(2))


def import_theme(root: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        if "theme.json" not in members:
            raise RuntimeError("压缩包缺少 theme.json")
        tmpdir = Path(tempfile.mkdtemp())
        try:
            zf.extractall(tmpdir)
            meta = json.loads((tmpdir / "theme.json").read_text(encoding="utf-8"))
            theme_id = meta["id"]
            label = meta["label"]
            script = meta["script"]

            for section in ("templates", "public"):
                source = tmpdir / section
                if not source.exists():
                    continue
                for item in source.rglob("*"):
                    if item.is_file():
                        rel = item.relative_to(source)
                        dest = root / section / rel
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(item, dest)
        finally:
            shutil.rmtree(tmpdir)

    safe_id = validate_theme_id(theme_id)
    apply_patches(root, {safe_id: label}, {safe_id: script})


def export_theme(root: Path, theme_id: str, label: str, dest: Path):
    safe_id = validate_theme_id(theme_id)
    tpl_dir = root / "templates/joinmenu-so-nice" / safe_id
    pub_dir = root / "public/joinmenu-so-nice" / safe_id
    script_path = f"joinmenu-so-nice/{safe_id}/joinmenu.js"
    if not tpl_dir.exists() or not pub_dir.exists():
        raise RuntimeError("主题文件缺失，无法导出。")
    meta = {"id": theme_id, "label": label, "script": script_path}
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("theme.json", json.dumps(meta, ensure_ascii=False, indent=2))
        for section, folder in (("templates", tpl_dir), ("public", pub_dir)):
            base = Path(folder.parts[-2], folder.parts[-1])
            for item in folder.rglob("*"):
                if item.is_file():
                    rel = Path(section) / base / item.relative_to(folder)
                    zf.write(item, rel)


def pack_external_theme(source_dir: Path, theme_id: str, dest: Path):
    """
    将任意目录结构打包为可导入主题。
    目录需要包含:
      - joinmenu.js
      - *.hbs 模板
      - custom.css 等静态资源
    """
    joinmenu = next(source_dir.rglob("joinmenu.js"), None)
    if not joinmenu:
        raise RuntimeError("未找到 joinmenu.js")

    template_files = list(source_dir.glob("*.hbs"))
    if not template_files:
        template_files = list(source_dir.rglob("*.hbs"))
    if not template_files:
        raise RuntimeError("未找到任何 .hbs 模板")

    css_files = list(source_dir.glob("*.css"))
    if not css_files:
        css_files = list(source_dir.rglob("*.css"))
    if not css_files:
        raise RuntimeError("未找到任何 .css 文件")

    safe_id = validate_theme_id(theme_id)
    meta = {
        "id": theme_id,
        "label": theme_id.title(),
        "script": f"joinmenu-so-nice/{safe_id}/joinmenu.js",
    }

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("theme.json", json.dumps(meta, ensure_ascii=False, indent=2))
        # 写入 templates，统一放在 templates/joinmenu-so-nice/<id>/
        templates_root = Path("templates") / "joinmenu-so-nice" / safe_id
        for file in template_files:
            arcname = templates_root / file.name
            zf.write(file, arcname)
        # 写入 public/joinmenu-so-nice/<id>/
        public_root = Path("public") / "joinmenu-so-nice" / safe_id
        for file in css_files:
            arcname = public_root / file.name
            zf.write(file, arcname)
        zf.write(joinmenu, public_root / "joinmenu.js")


def write_marker(root: Path, config: Dict[str, str]):
    marker = root / MARKER_NAME
    data = {
        "tool_version": config.get("version", "unknown"),
        "installed_at": datetime.utcnow().isoformat() + "Z",
        "themes": config.get("default_themes", []),
    }
    marker.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_marker(root: Path) -> Optional[Dict[str, str]]:
    marker = root / MARKER_NAME
    if not marker.exists():
        return None
    try:
        return json.loads(marker.read_text(encoding="utf-8"))
    except Exception:
        return None
def remove_theme(root: Path, theme_id: str):
    safe_id = validate_theme_id(theme_id)
    tpl_dir = root / "templates/joinmenu-so-nice" / safe_id
    pub_dir = root / "public/joinmenu-so-nice" / safe_id
    if tpl_dir.exists():
        shutil.rmtree(tpl_dir)
    if pub_dir.exists():
        shutil.rmtree(pub_dir)

    foundry_path = root / "public/scripts/foundry.mjs"
    constants_path = root / "common/constants.mjs"
    if not foundry_path.exists() or not constants_path.exists():
        raise RuntimeError("未找到 foundry.mjs 或 constants.mjs。")

    for path in (foundry_path, constants_path):
        backup(path)
        content = path.read_text(encoding="utf-8")
        match = WORLD_PATTERN.search(content)
        if not match:
            continue
        mapping = load_mapping(match.group(2))
        if theme_id in mapping:
            del mapping[theme_id]
            block = dump_mapping(mapping)
            content = content[:match.start(2)] + block[1:-1] + content[match.end(2):]
            path.write_text(content, encoding="utf-8")
