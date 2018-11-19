#!/bin/bash
#

#PASSWORD=""
#security unlock-keychain -p $PASSWORD ~/Library/Keychains/login.keychain

echo "Wait 5s"
sleep 5
WDADIR="/Users/codeskyblue/Workspace/WebDriverAgent"
UDID="$1"
# 运行测试
xcodebuild -project $WDADIR/WebDriverAgent.xcodeproj -scheme WebDriverAgentRunner -destination "id=$UDID" test
