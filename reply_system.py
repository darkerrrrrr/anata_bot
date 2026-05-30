import discord
import io
import sys

# ─── 届いたメッセージに付く「返信方法を選ぶボタン」（View） ───
class ReceiveReplyView(discord.ui.View):
    def __init__(self, original_sender_id: int):
        # 💡 タイムアウトでのボタン破損を防ぐため期限を無限（None）に設定
        super().__init__(timeout=None)
        self.original_sender_id = original_sender_id

    @discord.ui.button(label="匿名で返信する", style=discord.ButtonStyle.primary)
    async def anonymous_reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(self.original_sender_id, is_anonymous_reply=True))

    @discord.ui.button(label="名前を出して返信する", style=discord.ButtonStyle.success)
    async def name_reply(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ReplyModal(self.original_sender_id, is_anonymous_reply=False))


# ─── 返信ボタンを押したときの入力画面（Modal） ───
class ReplyModal(discord.ui.Modal):
    def __init__(self, original_sender_id: int, is_anonymous_reply: bool):
        self.original_sender_id = original_sender_id
        self.is_anonymous_reply = is_anonymous_reply
        title_text = '返信：匿名（名前を隠す）' if is_anonymous_reply else '返信：通常（名前を出す）'
        super().__init__(title=title_text)

        self.letter_content = discord.ui.TextInput(
            label='返信メッセージ本文', 
            style=discord.TextStyle.long, 
            placeholder='返信したい文章を入力してください...',
            max_length=2000
        )
        self.add_item(self.letter_content)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=False)

        target_user = interaction.client.get_user(self.original_sender_id)
        if not target_user:
            try:
                target_user = await interaction.client.fetch_user(self.original_sender_id)
            except discord.DiscordException:
                await interaction.followup.send("❌ エラー：返信相手のユーザーが見つかりませんでした。", ephemeral=True)
                return

        try:
            sender = "匿名" if self.is_anonymous_reply else f"{interaction.user.display_name}さん"
            chat_message = f"【{sender}より、大切な想いが届いています】"
                
            plain_text_content = self.letter_content.value

            file_data = io.BytesIO(plain_text_content.encode('utf-8'))
            discord_file = discord.File(fp=file_data, filename="reply.txt")
            
            # 返信されたメッセージにも再度返信ボタン（View）を最初から混ぜて送信
            view = ReceiveReplyView(original_sender_id=interaction.user.id)
            await target_user.send(content=chat_message, file=discord_file, view=view)
            
            await interaction.followup.send(f"✅ 返信完了：相手のDMへ届けました。", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.followup.send("❌ エラー：相手がDMを閉じているため、返信できませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ 予期せぬエラーが発生しました: {e}", ephemeral=True)


# ─── bot.pyの送信処理（on_submit）の瞬間に割り込んで、最初からボタンを混ぜるフック関数 ───
async def hooked_on_submit(self, interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True, thinking=False)

    input_name = self.target_username.value.strip().lstrip('@')
    target_user = None

    for guild in interaction.client.guilds:
        member = discord.utils.get(guild.members, name=input_name)
        if member:
            target_user = member
            break

    if not target_user:
        await interaction.followup.send(
            f"❌ エラー：「{input_name}」が見つかりませんでした。\n"
            "※プロフィールの「ユーザー名（小文字の英数字）」を正確に入力してください。", 
            ephemeral=True
        )
        return

    try:
        sender = "匿名" if self.is_anonymous else f"{interaction.user.display_name}さん"
        chat_message = f"【{sender}より、大切な想いが届いています】"
            
        plain_text_content = self.letter_content.value

        file_data = io.BytesIO(plain_text_content.encode('utf-8'))
        discord_file = discord.File(fp=file_data, filename="letter.txt")
        
        # 💡 後付け編集（edit）ではなく、sendの瞬間に返信用のViewボタンを確実に引数（view=view）として混ぜて同時に送り出します
        view = ReceiveReplyView(original_sender_id=interaction.user.id)
        await target_user.send(content=chat_message, file=discord_file, view=view)
        
        await interaction.followup.send(f"✅ 送信完了：{target_user.display_name}さんのDMへ届けました。", ephemeral=True)
        
    except discord.Forbidden:
        await interaction.followup.send("❌ エラー：相手がDMを閉じているため、送信できませんでした。", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"⚠️ 予期せぬエラーが発生しました: {e}", ephemeral=True)


# ─── プログラム起動時に自動でbot.pyの送信処理をすり替える仕掛け ───
for mod_name, mod in list(sys.modules.items()):
    if mod and mod_name != __name__ and hasattr(mod, 'LetterModal'):
        mod.LetterModal.on_submit = hooked_on_submit
