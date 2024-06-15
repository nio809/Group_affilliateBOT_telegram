from pyrogram import Client
from pyrogram import raw
from pyrogram.errors import ChatAdminRequired, ChannelInvalid
from typing import Union
import asyncio
import json

class GetChatInviteLinkJoinersCount:
    async def get_chat_invite_link_joiners_count(self, client: "Client", chat_id: Union[int, str], invite_link: str) -> int:
        """Method to get count of members joined using an invite link."""
        try:
            chat_id = int(chat_id)  # Ensure chat_id is an integer
            peer = await client.resolve_peer(chat_id)
            r = await client.invoke(
                raw.functions.messages.GetChatInviteImporters(
                    peer=peer,
                    link=invite_link,
                    limit=1,
                    offset_date=0,
                    offset_user=raw.types.InputUserEmpty()
                )
            )
            return r.count
        except ChatAdminRequired:
            print(f"Admin privileges required for chat {chat_id}. Cannot retrieve data.")
        except ChannelInvalid:
            print(f"Invalid channel ID: {chat_id}. Skipping.")
        except Exception as e:
            print(f"An error occurred with chat {chat_id}: {e}")
        return 0  # Return 0 if there's an error or handle as appropriate for your application

async def process_groups(client):
    with open('user.json', 'r') as file:
        data = json.load(file)

    counter = GetChatInviteLinkJoinersCount()
    for entry in data:
        group_id = int(entry['group_id'])
        count = await counter.get_chat_invite_link_joiners_count(
            client, group_id, entry['invite_link']
        )
        entry['join_count'] = count
    
    with open('updated_users.json', 'w') as file:
        json.dump(data, file, indent=4)

async def main():
    api_id = '2545015'  # Replace with your actual api_id
    api_hash = 'e47ff631050c6a7285e64a2be5384b76'  # Replace with your actual api_hash
    async with Client("my_user_session", api_id, api_hash) as app:
        await process_groups(app)

if __name__ == "__main__":
    asyncio.run(main())
