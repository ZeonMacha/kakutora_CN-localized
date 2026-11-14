文本导出（JSON）
================

原先的 CSV 已经删掉。每条正文都是这三个字段：

  location  本文件内唯一。行号和类型合成一个值，例如 23/TALK、7/SCENARIO。
            同一行号和同一类型再出现时，从第二条起写成 1/name/2
  narrator  说话人。没有说话人时是空字符串。界面预制体这里写的是物体路径
  text      要翻译的原文

一篇一个文件，外面有 dir、type、info、entry。

  stories/json/     剧情脚本。按主线、角色、章节、脚本分目录
                    后补的生日回在 EventQuest/special_birthday/
                    泳装活动愿望编、训练编在 EventQuest/quest_10_04/
  items.json        道具名、说明、注释
  ui_*.json         章节、活动、邮件标题
  glossary/         专名。term 是词，definition 是释义
  tables/           好感度邮件、任务、加载提示等句子
  text_assets/      语音标题、秘密文书、从者台词、快捷留言、角色档案、从者闲聊
  web/              推特流、デイトラ、新闻、官网。article 是正文，chrome 是导航
  watchanime/       动画字幕
  prefabs/          Unity 界面文字
  ui_dll/           客户端 DLL 里的日文

剧情的 location 是「剧本原行号/命令」，例如 23/TALK。CSV 里曾经写成 21,32，逗号前面的命令序号已经去掉。
