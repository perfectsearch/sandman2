
def prompt_question(question):
    reply = str(input(question+' (y/n): ')).lower().strip()
    if len(reply) < 1:
        return prompt_question("Please enter y or n.")
    if reply[0] == 'y':
        return True
    if reply[0] == 'n':
        return False
    else:
        return prompt_question("Please enter y or n.")
