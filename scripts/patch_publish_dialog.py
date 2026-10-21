import sys

path = 'studio/h3h_studio/ui/github_publish_dialog.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    def _on_check_permissions_finished(self, success: bool, info: dict):
        has_push = info.get("has_push", False)
        role = info.get("role", "none")
        login = info.get("login", "")
        self.is_trusted_creator = has_push

        if has_push:
            self.role_banner.setText(f"\U0001f7e2 Режим: Доверенный создатель / Владелец ({login or 'Ключ мейкера'}) — Прямая публикация на Switch")
            self.role_banner.setStyleSheet("padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; background-color: #064E3B; color: #10B981; border: 1px solid #059669;")
            self.single_publish_btn.setText("\U0001f680 Опубликовать видеофон на GitHub")
            self.single_publish_btn.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 11px 24px; font-size: 13px;")
        else:
            label_text = f"\U0001f7e1 Режим: Участник сообщества ({login or 'Гость'}) — Публикация через модерацию заявок"
            self.role_banner.setText(label_text)
            self.role_banner.setStyleSheet("padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; background-color: #78350F; color: #FBBF24; border: 1px solid #D97706;")
            self.single_publish_btn.setText("\U0001f4e4 Отправить на модерацию в H3H")
            self.single_publish_btn.setStyleSheet("background-color: #F59E0B; color: #121418; font-weight: bold; padding: 11px 24px; font-size: 13px;")'''

replacement = '''    def _on_check_permissions_finished(self, success: bool, info: dict):
        has_push = info.get("has_push", False)
        role = info.get("role", "none")
        login = info.get("login", "")
        token = self.token_edit.text().strip()
        repo = self.repo_edit.text().strip() or GitHubPublisher.DEFAULT_REPO
        self.is_trusted_creator = has_push

        if has_push:
            self.role_banner.setText(f"\U0001f7e2 Режим: Доверенный создатель / Владелец ({login or 'Ключ мейкера'}) — Прямая публикация на Switch")
            self.role_banner.setStyleSheet("padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; background-color: #064E3B; color: #10B981; border: 1px solid #059669;")
            self.single_publish_btn.setText("\U0001f680 Опубликовать видеофон на GitHub")
            self.single_publish_btn.setStyleSheet("background-color: #00E5FF; color: #121418; font-weight: bold; padding: 11px 24px; font-size: 13px;")
            if token:
                GitHubPublisher.save_stored_credentials(token, login or self.default_user, repo)
        else:
            is_sgdb_key = len(token) == 32 and all(c in "0123456789abcdefABCDEF" for c in token)
            if is_sgdb_key:
                label_text = "\u26a0\ufe0f Внимание: Введен 32-значный ключ SteamGridDB! Для роли Владельца нужен GitHub Token (ghp_...)"
            else:
                label_text = f"\U0001f7e1 Режим: Участник сообщества ({login or 'Гость'}) — Публикация через модерацию заявок"
            self.role_banner.setText(label_text)
            self.role_banner.setStyleSheet("padding: 6px 10px; border-radius: 4px; font-weight: bold; font-size: 12px; background-color: #78350F; color: #FBBF24; border: 1px solid #D97706;")
            self.single_publish_btn.setText("\U0001f4e4 Отправить на модерацию в H3H")
            self.single_publish_btn.setStyleSheet("background-color: #F59E0B; color: #121418; font-weight: bold; padding: 11px 24px; font-size: 13px;")'''

assert target in text, "Target not found in github_publish_dialog.py"
new_text = text.replace(target, replacement)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Patch applied successfully!")
