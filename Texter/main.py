#!/usr/bin/env python
import os

x = int(input('\n\nHello! Please input iMessage Cell Number to Send!\n\n'))

print(x)

def get_words(file_path):
     with open('lyrics.txt', 'r') as f:
          text = f.readlines()[0]
          words = text.split()
     return words

def sendmessage(number, message):
     os.system('osascript script.scpt {} "{}"'.format(number, message))

if __name__ == '__main__':
     text = get_words('lyrics.txt')
     for line in text:
          sendmessage(x, line)
