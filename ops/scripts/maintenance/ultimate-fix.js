// 🚀 終極UI修復腳本
// 這是最全面的修復腳本，整合了所有最佳實踐
// 在瀏覽器控制台中運行此腳本

(function () {
    console.log('🚀 啟動終極UI修復腳本...')
    console.log('='.repeat(60))

    let fixCount = 0
    const fixes = []

    // 修復函數
    function addFix(name, success) {
        fixes.push({ name, success })
        if (success) fixCount++
        console.log(`${success ? '✅' : '❌'} ${name}`)
    }

    // 1. 環境檢查
    console.log('🔍 第一步：環境檢查')
    const isOnChatbotPage = window.location.pathname === '/chatbot'
    addFix('檢查是否在聊天機器人頁面', isOnChatbotPage)

    if (!isOnChatbotPage) {
        console.log('⚠️ 不在聊天機器人頁面，將自動跳轉...')
        setTimeout(() => {
            window.location.href = '/chatbot'
        }, 2000)
        return
    }

    // 2. 清除緩存
    console.log('\n🧹 第二步：清除緩存')
    try {
        localStorage.clear()
        sessionStorage.clear()
        addFix('清除本地存儲', true)
    } catch (e) {
        addFix('清除本地存儲', false)
        console.warn('清除緩存失敗:', e)
    }

    // 3. 強制隱藏干擾元素
    console.log('\n🚫 第三步：隱藏干擾元素')
    const interferingSelectors = [
        '.el-header',
        '.el-menu',
        '.el-menu-item',
        '.app-container:not(.chatbot-force-container)',
        '.app-header',
        'header:not(.chatbot-nav):not(.chatbot-header)',
        'nav:not(.nav-right):not(.chatbot-nav)',
        '.sidebar',
        '.el-container:not(.chatbot-force-container)',
        '.version-btn',
        '.el-main:not(.chat-area)',
        '.el-aside'
    ]

    let hiddenElements = 0
    interferingSelectors.forEach(selector => {
        try {
            const elements = document.querySelectorAll(selector)
            elements.forEach(el => {
                // 確保不隱藏聊天機器人自己的元素
                if (!el.closest('.chatbot-force-container') &&
                    !el.closest('.chatbot-page') &&
                    !el.closest('.chatbot-nav') &&
                    !el.classList.contains('chatbot-nav')) {

                    el.style.display = 'none'
                    el.style.visibility = 'hidden'
                    el.style.opacity = '0'
                    el.style.position = 'absolute'
                    el.style.left = '-9999px'
                    hiddenElements++
                }
            })
        } catch (e) {
            console.warn(`隱藏 ${selector} 時出錯:`, e)
        }
    })
    addFix(`隱藏 ${hiddenElements} 個干擾元素`, hiddenElements > 0)

    // 4. 檢查並修復聊天機器人容器
    console.log('\n🤖 第四步：修復聊天機器人容器')
    const containerSelectors = [
        '.chatbot-force-container',
        '.chatbot-page',
        '.chatbot-app'
    ]

    let containerFixed = false
    containerSelectors.forEach(selector => {
        const container = document.querySelector(selector)
        if (container) {
            // 強制設置容器樣式
            const styles = {
                position: 'fixed',
                top: '0',
                left: '0',
                width: '100vw',
                height: '100vh',
                zIndex: '999999',
                background: '#1a1a1a',
                color: '#ffffff',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif'
            }

            Object.assign(container.style, styles)
            containerFixed = true
            console.log(`   修復容器: ${selector}`)
        }
    })
    addFix('修復聊天機器人容器', containerFixed)

    // 5. 添加強制CSS規則
    console.log('\n🎨 第五步：添加強制CSS規則')
    const existingStyle = document.getElementById('ultimate-fix-styles')
    if (existingStyle) {
        existingStyle.remove()
    }

    const style = document.createElement('style')
    style.id = 'ultimate-fix-styles'
    style.textContent = `
        /* 終極強制隱藏規則 */
        .el-header,
        .el-menu,
        .el-menu-item,
        .app-container:not(.chatbot-force-container),
        .app-header,
        .sidebar,
        .el-container:not(.chatbot-force-container),
        .el-main:not(.chat-area),
        .el-aside {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
            position: absolute !important;
            left: -9999px !important;
            z-index: -1 !important;
        }
        
        /* 聊天機器人容器強制樣式 */
        .chatbot-force-container,
        .chatbot-page,
        .chatbot-app {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            z-index: 999999 !important;
            background: #1a1a1a !important;
            color: #ffffff !important;
            display: flex !important;
            flex-direction: column !important;
            overflow: hidden !important;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif !important;
        }
        
        /* 確保body沒有滾動條和邊距 */
        body {
            overflow: hidden !important;
            margin: 0 !important;
            padding: 0 !important;
            background: #1a1a1a !important;
        }
        
        /* 隱藏可能的滾動條 */
        html {
            overflow: hidden !important;
        }
        
        /* 確保聊天機器人導航正確顯示 */
        .chatbot-nav,
        .chatbot-header {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            position: relative !important;
            left: auto !important;
            z-index: auto !important;
        }
    `

    document.head.appendChild(style)
    addFix('添加強制CSS規則', true)

    // 6. 設置語言
    console.log('\n🌐 第六步：設置語言')
    try {
        const currentLang = localStorage.getItem('notegen-language') || 'zh-TW'
        localStorage.setItem('notegen-language', currentLang)
        addFix(`設置語言為 ${currentLang}`, true)
    } catch (e) {
        addFix('設置語言', false)
    }

    // 7. 強制重新渲染
    console.log('\n🔄 第七步：強制重新渲染')
    try {
        // 觸發重新渲染
        document.body.style.display = 'none'
        document.body.offsetHeight // 觸發重排
        document.body.style.display = ''
        addFix('強制重新渲染', true)
    } catch (e) {
        addFix('強制重新渲染', false)
    }

    // 8. 最終驗證
    console.log('\n✅ 第八步：最終驗證')
    setTimeout(() => {
        const chatbotContainer = document.querySelector('.chatbot-force-container, .chatbot-page, .chatbot-app')
        const visibleInterference = document.querySelectorAll('.el-header:not([style*="display: none"]), .el-menu:not([style*="display: none"])')

        const containerExists = !!chatbotContainer
        const noInterference = visibleInterference.length === 0

        addFix('聊天機器人容器存在', containerExists)
        addFix('沒有可見的干擾元素', noInterference)

        // 生成最終報告
        console.log('\n' + '='.repeat(60))
        console.log('🎉 終極修復完成！')
        console.log(`✅ 成功修復: ${fixCount}/${fixes.length}`)
        console.log('\n📋 修復摘要:')
        fixes.forEach(fix => {
            console.log(`   ${fix.success ? '✅' : '❌'} ${fix.name}`)
        })

        if (containerExists && noInterference) {
            console.log('\n🎊 恭喜！聊天機器人頁面應該現在正確顯示了！')
            console.log('🔍 如果仍有問題，請檢查:')
            console.log('   1. 是否需要硬刷新頁面 (Ctrl+F5)')
            console.log('   2. 是否有其他CSS文件覆蓋了樣式')
            console.log('   3. 瀏覽器控制台是否有錯誤信息')
        } else {
            console.log('\n⚠️ 仍有問題需要解決:')
            if (!containerExists) {
                console.log('   - 聊天機器人容器未找到，可能需要重新載入頁面')
            }
            if (!noInterference) {
                console.log('   - 仍有干擾元素可見，可能需要更強的CSS規則')
            }
        }

        console.log('\n🛠️ 可用的調試函數:')
        console.log('   - ultimateReload(): 清除所有緩存並重新載入')
        console.log('   - forceHideAll(): 強制隱藏所有可能的干擾元素')
        console.log('   - checkStatus(): 檢查當前狀態')

    }, 1000)

    // 提供調試函數
    window.ultimateReload = function () {
        console.log('🔄 執行終極重新載入...')
        localStorage.clear()
        sessionStorage.clear()

        // 清除所有可能的緩存
        if ('caches' in window) {
            caches.keys().then(names => {
                names.forEach(name => {
                    caches.delete(name)
                })
            })
        }

        setTimeout(() => {
            location.reload(true)
        }, 500)
    }

    window.forceHideAll = function () {
        console.log('🚫 強制隱藏所有干擾元素...')
        const allElements = document.querySelectorAll('*')
        let hiddenCount = 0

        allElements.forEach(el => {
            if (el.classList.contains('el-header') ||
                el.classList.contains('el-menu') ||
                el.classList.contains('app-header') ||
                (el.classList.contains('app-container') && !el.classList.contains('chatbot-force-container'))) {

                el.style.display = 'none'
                el.style.visibility = 'hidden'
                el.style.opacity = '0'
                hiddenCount++
            }
        })

        console.log(`✅ 強制隱藏了 ${hiddenCount} 個元素`)
    }

    window.checkStatus = function () {
        console.log('🔍 當前狀態檢查:')
        const container = document.querySelector('.chatbot-force-container, .chatbot-page, .chatbot-app')
        const interference = document.querySelectorAll('.el-header:not([style*="display: none"]), .el-menu:not([style*="display: none"])')

        console.log(`   - 聊天機器人容器: ${container ? '存在' : '不存在'}`)
        console.log(`   - 可見干擾元素: ${interference.length} 個`)
        console.log(`   - 當前URL: ${window.location.href}`)
        console.log(`   - 視窗大小: ${window.innerWidth}x${window.innerHeight}`)

        return {
            hasContainer: !!container,
            interferenceCount: interference.length,
            isOnChatbotPage: window.location.pathname === '/chatbot'
        }
    }

})()

console.log('💡 終極修復腳本已載入！如果需要重新載入，請運行: ultimateReload()')