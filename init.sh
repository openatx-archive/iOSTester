#! /bin/sh

PASSWORD="Ablaze12345."
security unlock-keychain -p $PASSWORD ~/Library/Keychains/login.keychain

iproxy $2 8100 $1 &

WDAPath=/Users/donglai/H56Automation/WebDriverAgent/WebDriverAgent.xcodeproj

xcodebuild -project $WDAPath -scheme WebDriverAgentRunner -destination "id=$1" test

