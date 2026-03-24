import sqlite3, tempfile, shutil, os

src = r'C:\Users\fanch\AppData\Local\Microsoft\Edge\User Data\Default\Network\Cookies'
tmpdir = tempfile.mkdtemp()
dst = os.path.join(tmpdir, 'Cookies')
shutil.copy2(src, dst)
conn = sqlite3.connect(dst)
cur = conn.cursor()
cur.execute("SELECT name, host_key FROM cookies WHERE host_key LIKE '%bilibili%' ORDER BY name")
for name, host in cur.fetchall():
    print(f'{host:30s} {name}')
conn.close()
shutil.rmtree(tmpdir)
