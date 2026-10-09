import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthStore {
  static const _s=FlutterSecureStorage(aOptions: AndroidOptions(encryptedSharedPreferences:true));
  static Future<String?> access()=>_s.read(key:'access_token');
  static Future<String?> refresh()=>_s.read(key:'refresh_token');
  static Future<bool> hasSession() async => (await refresh())!=null || (await access())!=null;
  static Future<void> save(Map<String,dynamic> r) async {
    if(r['access_token']!=null) await _s.write(key:'access_token',value:r['access_token'].toString());
    if(r['refresh_token']!=null) await _s.write(key:'refresh_token',value:r['refresh_token'].toString());
  }
  static Future<void> clear()=>_s.deleteAll();
}
