#!/usr/bin/env python3
"""
go-file: CLI tool untuk membuka file/folder langsung dari terminal.
Fitur: Case-insensitive + Path fragments + User selection + BUGFIX (Duplicate hasil dihilangkan)
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# ─── KONFIGURASI ───────────────────────────────────────────────────────────────
# Gunakan os.path.normpath untuk konsistensi format path
DEFAULT_SEARCH_DIRS = [
    os.path.normpath("D:/"),
    os.path.normpath("D:/Kuliah"),
    os.path.normpath("D:/DOCIUMENT"),
]

EXCLUDE_FOLDERS = {
    "windows",
    "program files",
    "program files (x86)",
    "programdata",
    "recovery",
    "system volume information",
    "$recycle.bin",
    "appdata",
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "dist",
    ".next",
}

MAX_DEPTH = 5


# ─── QUERY PARSER ────────────────────────────────────────────────────────────
def parse_query(query):
    """
    Parse query user untuk extract nama target dan path context.
    Contoh: 'kuliah/plup/project' -> ('project', ['kuliah', 'plup'])
    """
    normalized = query.strip().replace("\\", "/").strip("/")
    parts = [p for p in normalized.split("/") if p]

    if not parts:
        return "", []

    if len(parts) == 1:
        return parts[0], []

    return parts[-1], parts[:-1]


# ─── FUNGSI PENCARIAN ────────────────────────────────────────────────────────
def search_item(target_name, search_dirs=None, max_depth=None):
    """Mencari file/folder secara CASE-INSENSITIVE."""
    if search_dirs is None:
        search_dirs = DEFAULT_SEARCH_DIRS
    if max_depth is None:
        max_depth = MAX_DEPTH

    target_lower = target_name.strip().lower()
    results = []
    searched = set()

    for base_dir in search_dirs:
        if not os.path.isdir(base_dir):
            continue
        # Normalisasi path root untuk menghindari duplikasi pencarian
        base_dir = os.path.normcase(os.path.abspath(base_dir))
        _search_recursive(base_dir, target_lower, max_depth, results, searched, 0)

    return _deduplicate_results(results)


def _search_recursive(current_dir, target_lower, max_depth, results, searched, depth):
    """Rekursif mencari file/folder."""
    if depth > max_depth:
        return

    # Normalisasi path agar case-insensitive di Windows
    abs_path = os.path.normcase(os.path.abspath(current_dir))
    if abs_path in searched:
        return
    searched.add(abs_path)

    try:
        entries = os.listdir(current_dir)
    except (PermissionError, OSError):
        return

    for entry in entries:
        entry_path = os.path.join(current_dir, entry)

        # Case-insensitive match pada nama file/folder
        if target_lower in entry.lower():
            results.append(entry_path)

        # Rekursif ke subfolder
        if os.path.isdir(entry_path):
            folder_name = os.path.normcase(os.path.basename(entry_path))
            if folder_name not in EXCLUDE_FOLDERS:
                _search_recursive(
                    entry_path, target_lower, max_depth, results, searched, depth + 1
                )


def search_drives(target_name):
    """Mencari file/folder di seluruh drive."""
    target_lower = target_name.strip().lower()
    results = []
    searched = set()

    drives = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = f"{letter}:\\"
        if os.path.exists(drive):
            drives.append(os.path.normpath(drive))

    for d in DEFAULT_SEARCH_DIRS:
        if os.path.isdir(d) and os.path.normpath(d) not in drives:
            drives.append(os.path.normpath(d))

    for base_dir in drives:
        try:
            # Normalisasi sebelum memanggil recursive
            base_dir = os.path.normcase(os.path.abspath(base_dir))
            _search_recursive(base_dir, target_lower, MAX_DEPTH, results, searched, 0)
        except Exception:
            continue

    return _deduplicate_results(results)


def _deduplicate_results(results):
    """Menghilangkan duplikat path hasil pencarian (menghindari bug double entry)."""
    seen = set()
    unique_results = []
    for path in results:
        # normcase menangani case-sensitivity Windows
        p = os.path.normcase(os.path.abspath(path))
        if p not in seen:
            seen.add(p)
            unique_results.append(path)
    return unique_results


# ─── FILTER PATH CONTEXT ─────────────────────────────────────────────────────
def filter_by_path_context(results, path_context):
    """Filter hasil berdasarkan path context (case-insensitive)."""
    if not path_context:
        return results

    context_lower = [c.lower() for c in path_context]
    filtered = []

    for path in results:
        path_lower = path.lower()
        # Cek apakah SEMUA fragmen ada di path lengkap
        if all(fragment in path_lower for fragment in context_lower):
            filtered.append(path)

    return filtered


# ─── FORMAT & SORTING ────────────────────────────────────────────────────────
def format_results(results, target_name):
    """Urutkan hasil: exact match > startswith > partial, lalu berdasarkan kedalaman."""
    target_lower = target_name.lower()

    def sort_key(item):
        name = os.path.basename(item).lower()
        depth = len(Path(item).parts)

        if name == target_lower:
            return (0, depth, item)
        elif name.startswith(target_lower):
            return (1, depth, item)
        return (2, depth, item)

    return sorted(results, key=sort_key)


# ─── TAMPILKAN LIST & PILIH ──────────────────────────────────────────────────
def display_results(sorted_results, target_name, original_query, path_context):
    print(f"\n📂 Ditemukan {len(sorted_results)} hasil:\n")
    print(f"   🔎 Query: '{original_query}'")
    if path_context:
        print(f"   📁 Path context: {'/'.join(path_context)}")
    print(f"   🎯 Target: '{target_name}'\n")
    print("-" * 70)

    for i, path in enumerate(sorted_results, 1):
        icon = "📁" if os.path.isdir(path) else "📄"
        name = os.path.basename(path)
        print(f"  {i}. {icon} {name}")
        print(f"     📍 {path}")
        if i < len(sorted_results):
            print()

    print("-" * 70)


def ask_user_choice(sorted_results):
    while True:
        try:
            choice_input = input(
                f"\n👉 Pilih nomor (1-{len(sorted_results)}) atau ketik 'q' untuk batal: "
            ).strip()

            if choice_input.lower() in ["q", "quit", "exit"]:
                print("Dibatalkan.")
                return None

            if not choice_input:
                print("❌ Masukan kosong. Masukkan nomor yang valid.")
                continue

            choice = int(choice_input)
            if 1 <= choice <= len(sorted_results):
                return sorted_results[choice - 1]
            else:
                print(f"❌ Nomor harus antara 1 dan {len(sorted_results)}.")

        except ValueError:
            print("❌ Masukan tidak valid. Ketik nomor atau 'q' untuk batal.")
        except KeyboardInterrupt:
            print("\nDibatalkan.")
            return None


# ─── BUKA FILE/FOLDER ────────────────────────────────────────────────────────
def open_item(path):
    path = os.path.abspath(path)
    if not os.path.exists(path):
        print(f"\n❌ Path tidak ditemukan: {path}")
        return False

    print(f"\n✅ Membuka: {path}")
    try:
        if os.name == "nt":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.call(["open", path])
        else:
            subprocess.call(["xdg-open", path])
        return True
    except Exception as e:
        print(f"\n❌ Gagal membuka: {e}")
        return False


# ─── CLI ARGUMENTS ───────────────────────────────────────────────────────────
def build_parser():
    parser = argparse.ArgumentParser(
        prog="go-file",
        description="🚀 Buka file/folder langsung dari terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Contoh:
  go-file "project"                  # Cari semua 'project'
  go-file "kuliah/project"           # Cari 'project' yang path-nya ada 'kuliah'
  go-file "kuliah/plup/project.xlsx" # Kombinasi path context + nama file
  go-file "project" --auto           # Langsung buka hasil terbaik
  go-file "project" -t file          # Hanya cari file
        """,
    )
    parser.add_argument(
        "query", type=str, help="Nama atau path fragments (contoh: 'kuliah/plup/file')"
    )
    parser.add_argument(
        "-a", "--auto", action="store_true", help="Langsung buka hasil terbaik"
    )
    parser.add_argument(
        "-d", "--deep", action="store_true", help="Deep search ke semua drive"
    )
    parser.add_argument(
        "--dir", type=str, default=None, help="Cari hanya di direktori tertentu"
    )
    parser.add_argument(
        "--max-depth", type=int, default=MAX_DEPTH, help="Kedalaman pencarian"
    )
    parser.add_argument(
        "-t",
        "--type",
        type=str,
        default="both",
        choices=["file", "folder", "both"],
        help="Filter tipe",
    )
    return parser


# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    parser = build_parser()
    args = parser.parse_args()

    original_query = args.query
    target_name, path_context = parse_query(original_query)

    if not target_name:
        print("❌ Query kosong. Gunakan format: 'nama' atau 'path/nama'")
        sys.exit(1)

    print(f"\n🔍 Mencari: '{original_query}'")
    print(f"   📝 Target: '{target_name}'")
    if path_context:
        print(f"   📁 Path context: {'/'.join(path_context)}")

    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"\n❌ Direktori tidak ditemukan: {args.dir}")
            sys.exit(1)
        search_dirs = [os.path.normpath(args.dir)]
    else:
        search_dirs = DEFAULT_SEARCH_DIRS

    if args.deep:
        print("\n⏳ Deep search di semua drive...")
        results = search_drives(target_name)
    else:
        print("\n⏳ Mencari di folder umum...")
        results = search_item(target_name, search_dirs, args.max_depth)

    # Filter tipe
    if args.type == "file":
        results = [r for r in results if os.path.isfile(r)]
    elif args.type == "folder":
        results = [r for r in results if os.path.isdir(r)]

    # Filter path context
    if path_context:
        results = filter_by_path_context(results, path_context)

    if not results:
        print(f"\n❌ Tidak ditemukan hasil untuk '{original_query}'")
        sys.exit(1)

    sorted_results = format_results(results, target_name)

    if args.auto:
        best = sorted_results[0]
        print(f"\n✅ Hasil terbaik: {os.path.basename(best)}")
        open_item(best)
        return

    display_results(sorted_results, target_name, original_query, path_context)

    if len(sorted_results) == 1:
        chosen_path = sorted_results[0]
        print(f"\n📌 Hanya ada 1 hasil. Membuka: {chosen_path}")
        open_item(chosen_path)
    else:
        chosen_path = ask_user_choice(sorted_results)
        if chosen_path:
            open_item(chosen_path)


if __name__ == "__main__":
    main()
