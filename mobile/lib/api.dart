import 'dart:convert';
import 'package:http/http.dart' as http;
import 'auth_store.dart';

class Api {
  static const base=String.fromEnvironment('API_BASE',defaultValue:'http://10.0.2.2:8000');
  static Future<dynamic> call(String path,{String method='GET',Object? body,bool retry=true}) async {
    var t=await AuthStore.access();
    final req=http.Request(method,Uri.parse('$base$path'))..headers['Content-Type']='application/json';
    if(t!=null) req.headers['Authorization']='Bearer $t';
    if(body!=null) req.body=jsonEncode(body);
    final s=await req.send(); final txt=await s.stream.bytesToString();
    if(s.statusCode==401 && retry && await _refresh()) return call(path,method:method,body:body,retry:false);
    if(s.statusCode>=400) throw Exception(txt);
    return txt.isEmpty?null:jsonDecode(txt);
  }
  static Future<bool> _refresh() async {
    final r=await AuthStore.refresh(); if(r==null) return false;
    try {final res=await http.post(Uri.parse('$base/auth/refresh'),headers:{'Content-Type':'application/json'},body:jsonEncode({'refresh_token':r,'platform':'android-ios'})); if(res.statusCode>=400)return false; await AuthStore.save(Map<String,dynamic>.from(jsonDecode(res.body))); return true;} catch(_){return false;}
  }
}
