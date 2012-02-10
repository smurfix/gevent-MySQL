import geventmysql

conn = geventmysql.connect(host="127.0.0.1", user="test", password="test")

cursor = conn.cursor()
cursor.execute("create database if not exists test_nested")
cursor.execute("use test_nested")
cursor.execute("create table if not exists numbers(a int)")
cursor.execute("delete from numbers")
cursor.execute("insert into numbers(a) values (1),(2),(3),(4),(5)")
cursor.execute("SELECT * from numbers")

for a, in cursor.fetchall():
	cursor.execute("SELECT * from numbers")
	for b, in cursor.fetchall():
		print a,b


cursor.close()
conn.close()

        
