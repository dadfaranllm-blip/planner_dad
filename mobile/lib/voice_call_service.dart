import 'dart:convert';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:http/http.dart' as http;

class VoiceCallService {
  final String apiBase;
  final String token;
  RTCPeerConnection? peer;
  MediaStream? localStream;
  VoiceCallService(this.apiBase, this.token);
  Map<String,String> get headers => {'Authorization':'Bearer $token','Content-Type':'application/json'};

  Future<void> prepare() async {
    localStream = await navigator.mediaDevices.getUserMedia({'audio': true, 'video': false});
    peer = await createPeerConnection({'iceServers':[{'urls':'stun:stun.l.google.com:19302'}]});
    for (final track in localStream!.getTracks()) { await peer!.addTrack(track, localStream!); }
  }

  Future<String> start(String conversationId) async {
    final r=await http.post(Uri.parse('$apiBase/conversations/$conversationId/calls'),headers:headers);
    if(r.statusCode>=300) throw Exception('call start failed');
    return jsonDecode(r.body)['id'];
  }

  Future<void> end(String callId) async {
    await http.post(Uri.parse('$apiBase/calls/$callId/end'),headers:headers);
    await localStream?.dispose(); await peer?.close();
  }
}
