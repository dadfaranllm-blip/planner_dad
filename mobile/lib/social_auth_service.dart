import 'dart:io';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';
import 'api.dart';
import 'auth_store.dart';

class SocialAuthService {
  static const _googleServerClientId = String.fromEnvironment('GOOGLE_SERVER_CLIENT_ID');
  static const _appleClientId = String.fromEnvironment('APPLE_CLIENT_ID');
  static const _appleRedirectUri = String.fromEnvironment('APPLE_REDIRECT_URI');

  static Future<void> google() async {
    if (_googleServerClientId.isEmpty) throw Exception('GOOGLE_SERVER_CLIENT_ID is not configured');
    final signIn = GoogleSignIn(scopes: const ['email','profile'], serverClientId: _googleServerClientId);
    final account = await signIn.signIn();
    if (account == null) throw Exception('Google sign-in cancelled');
    final auth = await account.authentication;
    if (auth.idToken == null) throw Exception('Google id token missing');
    final r = Map<String,dynamic>.from(await Api.call('/auth/google/mobile',method:'POST',body:{
      'id_token': auth.idToken,
      'device_name': 'personal-phone',
      'platform': Platform.isAndroid ? 'android' : 'ios',
    }));
    await AuthStore.save(r);
  }

  static Future<void> apple() async {
    if (_appleClientId.isEmpty) throw Exception('APPLE_CLIENT_ID is not configured');
    final credential = await SignInWithApple.getAppleIDCredential(
      scopes: const [AppleIDAuthorizationScopes.email, AppleIDAuthorizationScopes.fullName],
      webAuthenticationOptions: Platform.isAndroid
          ? WebAuthenticationOptions(clientId:_appleClientId, redirectUri:Uri.parse(_appleRedirectUri))
          : null,
    );
    final token=credential.identityToken;
    if(token==null) throw Exception('Apple identity token missing');
    final r=Map<String,dynamic>.from(await Api.call('/auth/apple/mobile',method:'POST',body:{
      'identity_token':token,
      'first_name':credential.givenName,
      'last_name':credential.familyName,
      'device_name':'personal-phone',
      'platform':Platform.isAndroid?'android':'ios',
    }));
    await AuthStore.save(r);
  }
}
