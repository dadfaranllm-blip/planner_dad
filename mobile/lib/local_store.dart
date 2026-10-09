import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

class LocalStore {
  static Database? _db;
  static Future<Database> db() async {
    if (_db != null) return _db!;
    final path = join(await getDatabasesPath(), 'planner_local.db');
    _db = await openDatabase(path, version: 1, onCreate: (d, v) async {
      await d.execute('CREATE TABLE cache(kind TEXT NOT NULL, id TEXT NOT NULL, body TEXT NOT NULL, updated_at INTEGER NOT NULL, PRIMARY KEY(kind,id))');
      await d.execute('CREATE TABLE outbox(id INTEGER PRIMARY KEY AUTOINCREMENT, method TEXT NOT NULL, path TEXT NOT NULL, body TEXT, created_at INTEGER NOT NULL)');
      await d.execute('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)');
    });
    return _db!;
  }

  static Future<List<Map<String,dynamic>>> list(String kind) async {
    final d=await db();
    final rows=await d.query('cache',where:'kind=?',whereArgs:[kind],orderBy:'updated_at DESC');
    return rows.map((r)=>Map<String,dynamic>.from(jsonDecode(r['body'] as String))).toList();
  }

  static Future<void> replaceAll(String kind,List<dynamic> items) async {
    final d=await db(); final b=d.batch();
    b.delete('cache',where:'kind=?',whereArgs:[kind]);
    final ts=DateTime.now().millisecondsSinceEpoch;
    for(final raw in items){
      final x=Map<String,dynamic>.from(raw as Map);
      final id=(x['id']??'').toString(); if(id.isEmpty) continue;
      b.insert('cache',{'kind':kind,'id':id,'body':jsonEncode(x),'updated_at':ts},conflictAlgorithm:ConflictAlgorithm.replace);
    }
    await b.commit(noResult:true);
  }

  static Future<void> upsert(String kind,Map<String,dynamic> x) async {
    final d=await db();
    await d.insert('cache',{'kind':kind,'id':x['id'].toString(),'body':jsonEncode(x),'updated_at':DateTime.now().millisecondsSinceEpoch},conflictAlgorithm:ConflictAlgorithm.replace);
  }

  static Future<void> delete(String kind, String id) async {
    final d = await db();
    await d.delete('cache', where: 'kind=? AND id=?', whereArgs: [kind, id]);
  }

  static Future<void> enqueue(String method,String path,[Map<String,dynamic>? body]) async {
    final d=await db();
    await d.insert('outbox',{'method':method,'path':path,'body':body==null?null:jsonEncode(body),'created_at':DateTime.now().millisecondsSinceEpoch});
  }
  static Future<List<Map<String,dynamic>>> outbox() async => (await db()).query('outbox',orderBy:'id');
  static Future<void> removeOutbox(int id) async => (await db()).delete('outbox',where:'id=?',whereArgs:[id]);
  static Future<void> meta(String key,String value) async => (await db()).insert('meta',{'key':key,'value':value},conflictAlgorithm:ConflictAlgorithm.replace);
  static Future<String?> getMeta(String key) async {final r=await (await db()).query('meta',where:'key=?',whereArgs:[key],limit:1);return r.isEmpty?null:r.first['value'] as String?;}
}
