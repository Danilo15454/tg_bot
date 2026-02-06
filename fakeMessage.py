
def FMfromCall(call) -> FakeMessage:
    return FakeMessage(call.message.chat,call.from_user,call.data,call.message.message_id,call.message)

def FMfromRaw(chat_id,text) -> FakeMessage:
    return FakeMessage(FakeChat(chat_id),0,text,0,None)

class FakeChat:
    def __init__(self,cid):
        self.id = cid

class FakeMessage:
    def __init__(self, chat,user,data,mid,msg):
        self.chat = chat
        self.from_user = user
        self.text = data
        self.message_id = mid
        self.reply_to_message = msg