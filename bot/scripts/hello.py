#!/usr/bin/env python3
import sys

def main():
    """一个简单的脚本，接收参数并返回问候语"""
    # sys.argv[0] 是脚本名本身
    # sys.argv[1] 是第一个参数
    if len(sys.argv) > 1:
        name = ' '.join(sys.argv[1:])
        print(f"你好, {name}! 欢迎使用这个机器人框架。")
    else:
        print("你好, 世界! 你可以尝试输入 /hello 你的名字")

if __name__ == '__main__':
    main()