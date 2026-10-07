# Panduan Pengembangan AT Tools

AT Tools adalah kumpulan tool internal Agile Technica untuk ERPNext/HRMS. Setiap tool adalah **modul Frappe** sendiri, dan bisa diaktifkan atau dinonaktifkan per site.

## 1. Struktur Folder

Path di bawah ini relatif ke root repo (`apps/at_tools/`). Perhatikan ada tiga level `at_tools`: root repo, package app, dan modul core.

```
at_tools/                              # root repo (git)
├── README.md
├── docs/DEVELOPMENT.md                # dokumen ini
├── pyproject.toml
└── at_tools/                          # package app (hooks.py ada di sini)
    ├── hooks.py                       # hanya membaca sites/.at_tools/generated_hooks.json, jangan tambah hook di sini
    ├── tools.py                       # registry TOOLS, is_tool_enabled(), collect_hooks(), generate_hooks()
    ├── modules.txt                    # daftar modul Frappe (AT Tools, User Permission Tools, ...)
    ├── public/js/<modul>/<app>/       # JS form per modul, dipisah per app target
    │   └── user_permission_tools/erpnext/employee.js
    ├── at_tools/                      # modul "AT Tools" (core / settings)
    │   └── doctype/
    │       ├── at_tools_settings/     # Single DocType: daftar tool + aktivasi per site
    │       └── at_tool_setting/       # child table baris tool
    └── user_permission_tools/          # satu folder per tool
        ├── hooks.py                   # HOOKS milik tool ini (doc_events, doctype_js, ...)
        ├── install.py                 # install(): dijalankan saat tool diaktifkan di site
        ├── utils.py                   # helper: sync, get_template_items, is_enabled
        ├── doc_events/
        │   └── erpnext/employee.py    # handler doc_events, dipisah per app pemilik DocType
        └── doctype/                   # DocType milik tool ini
```

### Aturan penempatan

| Yang dibuat | Tempatnya |
|---|---|
| Modul/tool baru | Folder `at_tools/at_tools/<nama_modul>/` (sejajar dengan `hooks.py`) |
| DocType milik tool | `<modul>/doctype/<nama_doctype>/` |
| Hook (doc_events, doctype_js, dll) | `<modul>/hooks.py`, variabel `HOOKS` |
| Handler `doc_events` | `<modul>/doc_events/<app_pemilik_doctype>/<doctype>.py` |
| JS untuk form | `at_tools/public/js/<modul>/<app_target>/<doctype>.js` |
| Logic install (custom field, dll) | `<modul>/install.py`, fungsi `install()` |

Contoh: handler Employee dari ERPNext ada di `doc_events/erpnext/employee.py`, dan kalau nanti ada event untuk DocType milik HRMS, taruh di `doc_events/hrms/`.

## 2. Registry Tool (`tools.py`)

Setiap tool harus didaftarkan di `TOOLS`:

```python
TOOLS = {
	"User Permission Tools": {
		"install": "at_tools.user_permission_tools.install.install",
		"hooks": "at_tools.user_permission_tools.hooks",
	},
}
```

- **Key** adalah nama modul Frappe (sama dengan yang ada di `modules.txt`). Key ini dipakai sebagai nama tool di `is_tool_enabled()` dan di AT Tools Settings.
- **`install`** (opsional): fungsi yang dipanggil **sekali** saat tool diaktifkan di site. Dipakai untuk custom field, data awal, dan sebagainya.
- **`hooks`** (opsional): modul yang punya variabel `HOOKS`. Dikumpulkan ke `generated_hooks.py`.

Tool baru **wajib** ditambahkan ke `modules.txt` juga, supaya Frappe mengenali modulnya.

## 3. Aktivasi per Site

Status aktif tersimpan di Single DocType **AT Tools Settings**, jadi berlaku per site (setiap site punya database sendiri).

Admin (System Manager) mengaktifkan tool dari **AT Tools Settings** dengan mencentang kolom `Enabled`. Saat tool berubah dari nonaktif ke aktif, `install()` dijalankan otomatis.

Mematikan tool **tidak** menghapus custom field atau data yang sudah dibuat.

## 4. Fungsi `is_tool_enabled(tool)`

Lokasi: `at_tools/tools.py`

```python
from at_tools.tools import is_tool_enabled

is_tool_enabled("User Permission Tools")  # True / False
```

Fungsi ini membaca AT Tools Settings untuk site yang sedang aktif, lalu mengecek apakah baris `tool` berstatus `enabled`.

### Kapan dipakai

Gunakan di **setiap titik masuk** tool, karena hook yang terdaftar di `generated_hooks.py` berlaku global untuk semua site, bukan hanya site yang mengaktifkan tool:

- **Handler `doc_events`**: cek di awal fungsi, lalu `return` kalau nonaktif.
- **Scheduler, job background, dan whitelisted API**: cek di awal juga.
- **Fungsi yang dipanggil dari handler**: cukup cek di pintu masuknya.

### Contoh pemakaian

```python
# doc_events/erpnext/employee.py
from at_tools.tools import is_tool_enabled
from at_tools.user_permission_tools.utils import sync_employee_user_permissions


def on_update(doc, method=None):
	if not is_tool_enabled("User Permission Tools"):
		return

	sync_employee_user_permissions(doc)
```

Di `user_permission_tools/utils.py` ada wrapper `is_enabled()` yang sudah memanggil `is_tool_enabled("User Permission Tools")`. Pakai wrapper ini kalau berada dalam tool yang sama.

### Catatan

- `is_tool_enabled` membaca Single DocType setiap kali dipanggil, jadi cukup satu pengecekan di tiap handler, jangan di setiap baris.
- Jangan memakai nama tool yang tidak ada di `TOOLS`. Fungsi ini akan mengembalikan `False` tanpa error, dan itu mudah menyembunyikan typo.

## 5. Hooks per Modul (`HOOKS`)

Setiap modul mendefinisikan hook-nya di `hooks.py` masing-masing:

```python
# user_permission_tools/hooks.py
HOOKS = {
	"doc_events": {
		"Employee": {
			"on_update": "at_tools.user_permission_tools.doc_events.erpnext.employee.on_update",
		},
	},
	"doctype_js": {
		"Employee": "public/js/user_permission_tools/erpnext/employee.js",
	},
}
```

Key yang didukung sama seperti hook Frappe biasa: `doc_events`, `doctype_js`, `doctype_list_js`, `scheduler_events`, dan lainnya.

### Alur hooks

1. Developer menulis `HOOKS` di `<modul>/hooks.py`.
2. Admin klik **Generate Hooks** di AT Tools Settings.
3. `collect_hooks()` mengumpulkan `HOOKS` dari tool yang **aktif** di site itu.
4. Hasil ditulis ke `sites/.at_tools/generated_hooks.json` (lewat `generate_hooks()` di `tools.py`).
5. `at_tools/hooks.py` membaca file JSON itu lewat `load_generated_hooks()`, lalu Frappe memakainya.

Kalau dua tool memasang hook yang sama (misalnya dua handler untuk `Employee.on_update`), hasilnya digabung menjadi list tanpa duplikat.

**Setelah generate, restart bench** karena hooks dibaca saat proses start. Kalau hook tidak berubah walaupun sudah restart, jalankan `bench --site <site> clear-cache`.

### Kenapa file data, bukan `.py` yang di-commit

`sites/.at_tools/generated_hooks.json` **sengaja tidak ada di repo `at_tools`** — `sites/` ada di luar repo app ini sama sekali (bukan cuma di-`.gitignore`), jadi tidak mungkin ke-commit. Alasannya:

- `sites/` adalah direktori data bench yang persisten lintas deploy; `apps/` (termasuk repo ini) di-replace tiap `git pull`/deploy, jadi hasil generate yang dulu disimpan di dalam package app akan ikut hilang kalau tidak di-commit manual tiap kali.
- Format JSON lebih aman untuk file yang auto-generated (dibaca `json.load`, bukan `exec`/`import` modul Python).

Konsekuensinya: **deployment baru (clone repo baru / server baru) wajib klik Generate Hooks sekali** setelah site di-migrate, karena file datanya tidak ikut ter-clone. Ini pengganti catatan lama "generated_hooks.py harus di-commit".

## 6. Membuat Tool Baru: Checklist

1. Buat folder `at_tools/at_tools/<nama_modul>/` dengan `__init__.py`.
2. Tambahkan nama modul ke `modules.txt`.
3. Tambahkan DocType di `<modul>/doctype/` dengan `module` = nama modul.
4. Jika perlu custom field, tulis di `<modul>/install.py` dengan fungsi `install()`, pakai `create_custom_fields(..., update=True)`.
5. Daftarkan di `TOOLS` (`tools.py`) dengan key nama modul, `install`, dan `hooks`.
6. Buat `<modul>/hooks.py` dengan variabel `HOOKS`.
7. Tulis handler di `<modul>/doc_events/<app>/<doctype>.py`, dan cek `is_tool_enabled()` di awal fungsi.
8. Jika ada JS, taruh di `at_tools/public/js/<modul>/<app>/<doctype>.js`, lalu daftarkan di `HOOKS["doctype_js"]`.
9. Migrate: `bench --site <site> migrate`.
10. Di AT Tools Settings: aktifkan tool, lalu klik **Generate Hooks**.
11. Jalankan `bench build --app at_tools` kalau ada JS baru, lalu restart bench.

## 7. Hal yang Perlu Diingat

- **Install tidak otomatis ulang.** `install()` hanya jalan saat tool baru diaktifkan. Kalau Anda menambah field di `install()` untuk site yang sudah aktif, nonaktifkan lalu aktifkan lagi tool-nya, atau panggil `install()` manual.
- **`sites/.at_tools/generated_hooks.json` tidak ikut ke-clone/deploy.** Deployment baru (atau site baru) harus klik **Generate Hooks** sekali setelah tool diaktifkan, baru hooks berfungsi.
- **Generate membaca tool yang aktif di site tempat tombol diklik.** File ini dipakai untuk seluruh bench, jadi kalau beberapa site punya setelan berbeda, hasilnya bisa tidak sesuai untuk site lain. Handler tetap dicek dengan `is_tool_enabled`, jadi tool yang mati tidak akan berjalan.
- **Error di handler `doc_events` membatalkan save dokumennya.** Handler sync User Permission ikut dalam transaksi save Employee, jadi error akan membatalkan save. Validasi input sebisa mungkin di level template (`validate`), bukan saat sync.
- **`modified` tidak boleh diubah saat sync.** Pakai `frappe.db.set_value(..., update_modified=False)` di handler yang menulis ke dokumen yang sedang disimpan, supaya save berikutnya dari form tidak kena `TimestampMismatchError`.
- **Field `name` (ID Employee) hanya bisa dipakai dengan Allow = Employee** di User Permission Template.
- **ERPNext otomatis membuat User Permission** untuk Employee yang punya `user_id`: `Company = <company>` dan `Employee = <diri sendiri>`. Sync tool tidak membuat ulang UP yang sudah ada, dan tidak akan menghapusnya.
