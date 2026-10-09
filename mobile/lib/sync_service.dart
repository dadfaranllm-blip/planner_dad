import 'dart:convert';
import 'package:flutter/services.dart';
import 'api.dart';
import 'local_store.dart';

class SyncService {
  static const _widget=MethodChannel('planner/widget');
  static Future<void> sync() async {
    for(final op in await LocalStore.outbox()){
      try{
        final raw=op['body'] as String?;
        await Api.call(op['path'] as String,method:op['method'] as String,body:raw==null?null:jsonDecode(raw));
        await LocalStore.removeOutbox(op['id'] as int);
      } catch(_) { break; }
    }
    try{
      final r=await Future.wait([
        Api.call('/tasks'), Api.call('/events'), Api.call('/workspaces/summary'), Api.call('/conversations')
      ]);
      await LocalStore.replaceAll('task',List<dynamic>.from(r[0]??[]));
      await LocalStore.replaceAll('event',List<dynamic>.from(r[1]??[]));
      await LocalStore.replaceAll('workspace',List<dynamic>.from(r[2]??[]));
      await LocalStore.replaceAll('conversation',List<dynamic>.from(r[3]??[]));
      await LocalStore.meta('last_sync',DateTime.now().toIso8601String());
      await updateWidget();
    }catch(_){/* Local-first: cached data stays usable while offline. */}
  }

  static Future<void> updateWidget() async {
    final tasks=await LocalStore.list('task'); final events=await LocalStore.list('event');
    try{await _widget.invokeMethod('setWidgetData',{'tasks':jsonEncode(tasks),'events':jsonEncode(events)});}catch(_){ }
  }
}
