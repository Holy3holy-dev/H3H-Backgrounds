from pathlib import Path

p = Path("scripts/auto_harvest_pipeline.py")
text = p.read_text(encoding="utf-8")

old_prompt = '''def prompt_new_gdrive_token() -> str:
    """Interactive recovery handler when Google Drive access token expires."""
    print("\\n" + "=" * 68)
    print("  🔑 [ВНИМАНИЕ] Срок действия токена Google Drive (1 час) истек!")
    print("=" * 68)
    print("  1. Зайдите в Google OAuth Playground (developers.google.com/oauthplayground)")
    print("     или откройте H3H-Studio -> 'Управление каталогом'.")
    print("  2. В OAuth Playground нажмите кнопку 'Refresh access token' (или Exchange)")
    print("     и скопируйте новый Access token (начинается с ya29...).")
    print("  3. Вставьте его сюда и нажмите Enter:")
    print("=" * 68)

    while True:
        try:
            val = input(">> Вставьте новый Access Token (ya29...): ").strip()
        except (EOFError, KeyboardInterrupt):
            val = ""

        if not val:
            # Re-read from disk in case user saved it in studio or file
            cfg_tok, _ = get_gdrive_credentials()
            val = cfg_tok

        print("  [*] Проверка токена связи с Google Drive...")
        res = GoogleDriveClient.test_connection(val)
        if res.get("ok"):
            user_name = res.get("displayName") or res.get("user") or "Успешно"
            print(f"  [✓] Авторизация успешна! Аккаунт: {user_name}\\n")
            save_gdrive_token(val)
            return val
        else:
            err = res.get("error", "Неверный токен")
            print(f"  [-] Токен не подошел: {err}. Пожалуйста, попробуйте еще раз.")'''

new_prompt = '''def prompt_new_gdrive_token() -> str:
    """Interactive recovery handler when Google Drive access token expires."""
    # 1. First, check if we have a saved refresh_token that can automatically give us a fresh token
    if GDRIVE_CFG_PATH.exists():
        try:
            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
            saved_ref = cfg.get("refresh_token")
            if saved_ref:
                print("  [*] Попытка автоматического обновления токена через сохраненный Refresh Token...")
                auto_tok = GoogleDriveHelper.refresh_access_token(saved_ref)
                if auto_tok:
                    res = GoogleDriveClient.test_connection(auto_tok)
                    if res.get("ok"):
                        print(f"  [✓] Токен автоматически обновлен без вашего участия! Аккаунт: {res.get('user', 'OK')}\\n")
                        save_gdrive_token(auto_tok)
                        return auto_tok
        except Exception:
            pass

    print("\\n" + "=" * 70)
    print("  🔑 [ВНИМАНИЕ] Срок действия токена Google Drive (1 час) истек!")
    print("=" * 70)
    print("  Как решить проблему НАВСЕГДА (чтобы не вводить каждый час):")
    print("  1. В Google OAuth Playground (Step 2) скопируйте поле 'Refresh token'")
    print("     (начинается с 1//04... или 1//0...) и вставьте его сюда.")
    print("     Скрипт сохранит его и будет САМ обновлять токены вечно в фоне!")
    print()
    print("  Либо скопируйте обычный 'Access token' (ya29... - действует 1 час).")
    print("=" * 70)

    while True:
        try:
            val = input(">> Вставьте Refresh Token (1//...) или Access Token (ya29...): ").strip()
        except (EOFError, KeyboardInterrupt):
            val = ""

        if not val:
            # Re-read from disk in case user updated file
            cfg_tok, _ = get_gdrive_credentials()
            val = cfg_tok

        # If user entered a Refresh token starting with 1//
        if val.startswith("1//") or val.startswith("1/"):
            print("  [*] Пробуем получить постоянный доступ через введенный Refresh Token...")
            new_acc_tok = GoogleDriveHelper.refresh_access_token(val)
            if new_acc_tok:
                test_res = GoogleDriveClient.test_connection(new_acc_tok)
                if test_res.get("ok"):
                    # Save both refresh_token and token permanently!
                    try:
                        cfg = {}
                        if GDRIVE_CFG_PATH.exists():
                            cfg = json.loads(GDRIVE_CFG_PATH.read_text(encoding="utf-8"))
                        cfg["refresh_token"] = val
                        cfg["token"] = new_acc_tok
                        GDRIVE_CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
                    except Exception:
                        pass
                    user_name = test_res.get("displayName") or test_res.get("user") or "Успешно"
                    print(f"  🎉 [УСПЕХ] Refresh Token сохранен! Доступ настроен НАВСЕГДА!")
                    print(f"  Аккаунт: {user_name}. Теперь токены будут обновляться сами без вопросов.\\n")
                    return new_acc_tok
            print("  [-] Не удалось обновить токен через этот Refresh Token. Попробуйте еще раз.")
            continue

        print("  [*] Проверка токена связи с Google Drive...")
        res = GoogleDriveClient.test_connection(val)
        if res.get("ok"):
            user_name = res.get("displayName") or res.get("user") or "Успешно"
            print(f"  [✓] Авторизация успешна! Аккаунт: {user_name}\\n")
            save_gdrive_token(val)
            return val
        else:
            err = res.get("error", "Неверный токен")
            print(f"  [-] Токен не подошел: {err}. Пожалуйста, попробуйте еще раз.")'''

assert old_prompt in text, "old_prompt not found in auto_harvest_pipeline.py"
text = text.replace(old_prompt, new_prompt)
p.write_text(text, encoding="utf-8")
print("auto_harvest_pipeline.py successfully updated with permanent Refresh Token support!")
