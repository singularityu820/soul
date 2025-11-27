import { LAppDelegate } from './lappdelegate';
import { LAppLive2DManager } from './lapplive2dmanager';
import * as LAppDefine from './lappdefine';
import React, { useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import './asset/index.css'

const ReactLive2d = forwardRef(function ReactLive2d(props, ref) {

    // 好看颜色列表
    // green: '#B4DEAE',
    // DeepBlue: '#5B8DBE',
    // LightBlue: '#C8E6FE',
    // pink: '#F9B8BE'

    // 容器样式
    let containerStyle = {
        position: 'fixed',
        top: props.top ? props.top : '',
        right: props.right ? props.right : '0',
        bottom: props.bottom ? props.bottom : '0',
        left: props.left ? props.left : ''
    }
    // canvas样式
    let canvasStyle = {
        position: 'relative',
        top: props.top ? props.top : '',
        right: props.right ? props.right : '0',
        bottom: props.bottom ? props.bottom : '0',
        left: props.left ? props.left : ''
    }
    // 对话框样式 - 可爱风格（根据内容自适应大小）
    let printStyle = {
        position: 'absolute',
        width: 'auto',
        height: 'auto',
        minWidth: '80px',
        maxWidth: '280px',
        minHeight: '50px',
        maxHeight: 'none',
        left: '50%',
        transform: 'translateX(-50%) translateY(10px) scale(0.9)',
        top: '-40px',
        borderRadius: '24px',
        border: '3px solid rgba(255, 182, 193, 0.6)',
        padding: '14px 18px',
        background: 'linear-gradient(135deg, rgba(255, 240, 245, 0.98) 0%, rgba(255, 228, 225, 0.95) 50%, rgba(255, 240, 245, 0.98) 100%)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        boxShadow: '0 10px 40px rgba(255, 182, 193, 0.25), 0 4px 12px rgba(255, 105, 180, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.6)',
        display: 'none',
        color: '#8B4A6B',
        fontSize: '15px',
        lineHeight: '1.6',
        fontWeight: '600',
        textAlign: 'center',
        wordWrap: 'break-word',
        wordBreak: 'break-word',
        whiteSpace: 'normal',
        boxSizing: 'border-box',
        zIndex: 1000,
        opacity: 0,
        transition: 'opacity 0.35s cubic-bezier(0.34, 1.56, 0.64, 1), transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)',
    }

    // 面板主题样式
    let Theme = {
        color: props.color ? props.color : '#C8E6FE',
        width: '30px',
        height: '30px',
    }

    let timer = null;

    const [controllerOn, setControllerOn] = useState(false)

    const [controllerIn, setControllerIn] = useState(false)

    const [printMenu, setPrintMenu] = useState(false)

    // 进入显示控制台
    function cvMouseOver() {
        setControllerOn(true)
    }

    function cvMouseOut() {
        timer = setTimeout(() => {
            // 0.01秒内没有进入点击面板，说明已经鼠标离开
            if (!controllerIn) {
                setControllerOn(false)
                setControllerIn(false)
            }
        }, 10);
    }

    // 进入选择菜单
    function ctMouseOver() {
        setControllerIn(true)
        clearTimeout(timer)
    }

    // 离开选择菜单
    function ctMouseOut() {
        setControllerIn(false)
    }

    //切换
    function ctTab() {
        LAppLive2DManager.getInstance().nextScene();
    }

    // 悬停菜单时的对白
    function talkPrint(print) {
        let printNow = document.getElementById('live2d-print');
        if (printNow) {
            // 确保结构完整：获取或创建内容元素
            let content = printNow.querySelector('.live2d-print-content');
            
            // 如果内容元素不存在，创建它
            if (!content) {
                content = document.createElement('div');
                content.className = 'live2d-print-content';
                printNow.appendChild(content);
            }
            
            const hasContent = content.innerHTML.trim() !== '';
            
            // 如果有旧内容，先向上渐隐消失
            if (hasContent) {
                // 添加向上渐隐动画类
                printNow.classList.add('live2d-print-fade-up');
                
                // 等待动画完成后显示新内容
                setTimeout(() => {
                    // 更新内容
                    content.innerHTML = print;
                    
                    // 移除渐隐动画类，准备显示新内容
                    printNow.classList.remove('live2d-print-fade-up');
                    
                    // 确保初始状态正确（用于新内容的进入动画）
                    printNow.style.opacity = '0';
                    printNow.style.transform = 'translateX(-50%) translateY(10px) scale(0.9)';
                    printNow.style.display = 'block';
                    
                    // 触发新内容的进入动画
                    setTimeout(() => {
                        printNow.style.opacity = '1';
                        printNow.style.transform = 'translateX(-50%) translateY(0) scale(1)';
                    }, 10);
                }, 300); // 等待渐隐动画完成
            } else {
                // 如果没有旧内容，直接显示新内容
                content.innerHTML = print;
                
                // 确保初始状态正确
                printNow.style.opacity = '0';
                printNow.style.transform = 'translateX(-50%) translateY(10px) scale(0.9)';
                printNow.style.display = 'block';
                
                // 触发进入动画
                setTimeout(() => {
                    printNow.style.opacity = '1';
                    printNow.style.transform = 'translateX(-50%) translateY(0) scale(1)';
                }, 10);
            }
        }
    }

    function cancelPrint() {
        let printNow = document.getElementById('live2d-print');
        if (printNow) {
            // 先触发淡出动画
            printNow.style.opacity = '0';
            printNow.style.transform = 'translateX(-50%) translateY(10px) scale(0.9)';
            // 动画完成后隐藏并清空内容
            setTimeout(() => {
                const content = printNow.querySelector('.live2d-print-content');
                if (content) {
                    content.innerHTML = '';
                }
                printNow.style.display = 'none';
            }, 300);
        }
    }

    // 暴露函数给父组件
    useImperativeHandle(ref, () => ({
        talkPrint: talkPrint,
        cancelPrint: cancelPrint
    }));

    useEffect(() => {
        console.log('ReactLive2d component mounted')

        props.ModelList ? LAppDefine.lappdefineSet.setModelDir(props.ModelList) : LAppDefine.lappdefineSet.setModelDir([])
        props.TouchBody ? LAppDefine.lappdefineSet.setHitBody(props.TouchBody) : LAppDefine.lappdefineSet.setHitBody([])
        props.TouchHead ? LAppDefine.lappdefineSet.setHitHead(props.TouchHead) : LAppDefine.lappdefineSet.setHitHead([])
        props.TouchDefault ? LAppDefine.lappdefineSet.setHitDefault(props.TouchDefault) : LAppDefine.lappdefineSet.setHitDefault([])
        props.PathFull ? LAppDefine.lappdefineSet.setPathFull(props.PathFull) : LAppDefine.lappdefineSet.setPathFull('')

        if (!navigator.userAgent.match(/mobile/i) || props.MobileShow == true) {
            // 如果已经初始化过，先释放再重新初始化
            try {
                LAppDelegate.releaseInstance();
            } catch (error) {
                console.warn('Error releasing existing instance:', error);
            }

            if (LAppDelegate.getInstance().initialize() == false) {
                console.error('Failed to initialize Live2D');
                return;
            }

            LAppDelegate.getInstance().run();
            console.log('Live2D initialized and running');
        }

        // 清理函数：组件卸载时释放资源
        return () => {
            console.log('ReactLive2d component unmounting, cleaning up...');
            // 清理弹框
            const printNow = document.getElementById('live2d-print');
            if (printNow) {
                printNow.style.display = 'none';
                const content = printNow.querySelector('.live2d-print-content');
                if (content) {
                    content.innerHTML = '';
                }
            }
            // 释放 Live2D 实例
            try {
                LAppDelegate.releaseInstance();
                console.log('Live2D instance released');
            } catch (error) {
                console.warn('Error releasing Live2D instance:', error);
            }
        };
    }, []);

    useEffect(() =>{
        if(props.release==true){
            LAppDelegate.releaseInstance();
        }
    }, [props.release])

    return (
        <div>
            <div
                style={containerStyle}
                width={props.width ? props.width : '300'}
                height={props.height ? props.height : '500'}
                id="live2d-container">
                <div id="live2d-hidden"
                    style={{
                        width:'100%',
                        height:'100%',
                        position:'absolute',
                        top:'0',
                        left:'0',
                        zIndex:'2'
                    }}
                >

                </div>
                {props.Modal ?? (
                    <div id="live2d-print"
                         className="live2d-print-bubble"
                         style={printStyle}
                    >
                        <div className="live2d-print-content"></div>
                    </div>
                )}
                <canvas
                    id="live2d"
                    style={canvasStyle}
                    width={props.width ? props.width : '300'}
                    height={props.height ? props.height : '500'}
                    className="live2d"
                    onMouseEnter={cvMouseOver}
                    onMouseLeave={cvMouseOut}
                >

                </canvas>
                {/* {controllerOn && (!props.menuList || props.menuList.length>0) &&
                    <div
                        className="live2d-controller"
                        style={{
                            position: 'absolute',
                            top: '20px',
                            left: '20px',
                        }}
                        // onMouseEnter={ctMouseOver}
                        // onMouseLeave={ctMouseOut}
                    >
                        {(!props.menuList || props.menuList.indexOf('Mtab')>-1) &&
                            <div
                                className="iconfont"
                                style={Theme}
                                onClick={ctTab}
                                onMouseEnter={()=>talkPrint('你想要换一个看板娘吗？')}
                                onMouseLeave={cancelPrint}
                            >&#xe7ca;</div>
                        }
                    </div>
                } */}
            </div>
        </div>
    )
});

export default ReactLive2d