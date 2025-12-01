import React, { useEffect, useRef, useState } from "react";
import "./styles/index.css";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { TextureLoader } from "three";
import moonModelPath from "./styles/img/the_old_moon/scene.gltf?url";
import roseModelPath from "./styles/img/rose/scene.gltf?url";
import princeModelPath from "./styles/img/lowpoly_fox/scene.gltf?url";
import Modal from "../../components/ui/Modal.jsx";
import Inventory from "../../components/Inventory.jsx";

// Unity iframe 配置
const UNITY_IFRAME_URL = "https://soul-game-gzip-vercel.vercel.app/";
// 提取 origin（用于消息来源验证）
const UNITY_IFRAME_ORIGIN = new URL(UNITY_IFRAME_URL).origin;

export default function StarPortalPlanB() {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const particlesRef = useRef(null);
  const materialRef = useRef(null);
  const moonRef = useRef(null);
  const roseRef = useRef(null);
  const princeRef = useRef(null);
  const animationFrameRef = useRef(null);
  const raycasterRef = useRef(null); // 射线检测器
  const cursorRoseRef = useRef(null); // 跟随鼠标的玫瑰模型
  const plantedRosesRef = useRef([]); // 存储所有种植的玫瑰
  
  // 控制显示哪个模型：'prince' 或 'moon-rose'
  const [currentModel, setCurrentModel] = useState('prince');
  const currentModelRef = useRef('prince'); // 用于在渲染循环中访问最新值
  
  // 控制是否点击了玫瑰（用于触发俯视视角）
  const [roseClicked, setRoseClicked] = useState(false);
  const roseClickedRef = useRef(false);
  
  // 控制全屏弹框显示
  const [showUnityModal, setShowUnityModal] = useState(false);
  const [isVideoLoaded, setIsVideoLoaded] = useState(false); // 视频加载完成状态
  const [showEndVideo, setShowEndVideo] = useState(false); // 控制是否显示结束视频
  const iframeRef = useRef(null);
  const videoRef = useRef(null); // 视频引用
  const endVideoRef = useRef(null); // 结束视频引用
  
  // 控制物品栏显示和折叠状态
  const [showInventory, setShowInventory] = useState(true);
  const [inventoryCollapsed, setInventoryCollapsed] = useState(false);
  
  // 物品栏数据
  const [inventoryItems, setInventoryItems] = useState([
    // { id: 1, name: '玫瑰', icon: null, count: 1, description: '一朵美丽的玫瑰' },
    // { id: 2, name: '星星', icon: null, count: 5, description: '闪烁的星星' },
  ]);
  
  // 控制是否正在携带玫瑰（跟随鼠标）
  const [isCarryingRose, setIsCarryingRose] = useState(false);
  const isCarryingRoseRef = useRef(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  
  // 记录点击玫瑰时的相机状态，用于检测用户是否改变了视角
  const roseClickedCameraStateRef = useRef({
    radius: 0,
    theta: 0,
    phi: 0
  });
  
  // 小王子的初始视角值（用户调整后的值）
  const princeInitialViewRef = useRef({
    radius: 260,
    theta: Math.PI / 4,
    phi: Math.PI / 2
  });
  
  // 标记是否正在恢复视角到初始值（点击小王子后）
  const isRestoringViewRef = useRef(false);
  
  // 模型加载状态标记
  const moonLoadedRef = useRef(false);
  const roseLoadedRef = useRef(false);
  const isLoadingMoonRoseRef = useRef(false); // 加载锁，防止重复加载
  const princeLoadedRef = useRef(false);
  
  // 存储模型加载函数，用于重新加载
  const loadMoonRoseRef = useRef(null);
  
  // 使用球坐标系控制相机
  const cameraSphericalRef = useRef({ 
    radius: 260, // 相机到小王子的距离
    theta: Math.PI / 4,    // 水平角度（左右旋转，0到2π），初始设置为60度
    phi: Math.PI / 2  // 垂直角度（上下旋转，0到π，π/2是水平）
  });
  const targetSphericalRef = useRef({ 
    radius: 260,
    theta: Math.PI / 4, // 初始设置为60度
    phi: Math.PI / 2
  });
  const windowHalfXRef = useRef(window.innerWidth / 2);
  const windowHalfYRef = useRef(window.innerHeight / 2);
  const isDraggingRef = useRef(false); // 是否正在拖动
  const lastMouseXRef = useRef(0); // 上一次鼠标X位置
  const lastMouseYRef = useRef(0); // 上一次鼠标Y位置
  const dragStartXRef = useRef(0); // 拖动开始时的X位置
  const dragStartYRef = useRef(0); // 拖动开始时的Y位置

  useEffect(() => {
    console.log('inventoryItems', inventoryItems);
  }, [inventoryItems]);

  // 同步currentModel到ref，并更新模型可见性
  useEffect(() => {
    currentModelRef.current = currentModel;
    
    // 如果切换到moon-rose，检查模型是否需要加载
    if (currentModel === 'moon-rose') {
      console.log('Switching to moon-rose, checking if models need to be loaded...');
      
      // 验证模型是否完整存在的辅助函数
      const validateModelExists = () => {
        const scene = sceneRef.current;
        if (!scene) return { moonValid: false, roseValid: false };
        
        // 检查月球是否存在且完整
        const moonValid = moonRef.current && 
                         moonLoadedRef.current && 
                         scene.children.includes(moonRef.current) &&
                         moonRef.current.children.length >= 0; // 至少存在（玫瑰可能还没加载）
        
        // 检查玫瑰是否存在且完整（包括纹理）
        let roseValid = false;
        if (roseRef.current && roseLoadedRef.current) {
          // 检查玫瑰是否在月球的子对象中
          const roseInMoon = moonRef.current?.children.includes(roseRef.current);
          // 检查玫瑰是否有纹理（验证模型完整性）
          let hasTexture = false;
          if (roseRef.current) {
            roseRef.current.traverse((child) => {
              if (child.isMesh && child.material) {
                const mat = Array.isArray(child.material) ? child.material[0] : child.material;
                if (mat && mat.map) {
                  hasTexture = true;
                }
              }
            });
          }
          roseValid = roseInMoon && hasTexture;
        }
        
        return { moonValid, roseValid };
      };
      
      const { moonValid, roseValid } = validateModelExists();
      
      console.log('Model check - Moon valid:', moonValid, 'Rose valid:', roseValid, 'Is loading:', isLoadingMoonRoseRef.current);
      
      // 只有在模型不存在、不完整或正在加载时才重新加载
      if ((!moonValid || !roseValid) && !isLoadingMoonRoseRef.current) {
        console.log('Models missing or incomplete, reloading...');
        // 如果加载函数存在，调用它重新加载
        // 使用 setTimeout 确保在下一帧执行，避免与当前渲染冲突
        setTimeout(() => {
          if (loadMoonRoseRef.current) {
            loadMoonRoseRef.current();
          }
        }, 0);
      } else if (moonValid && roseValid) {
        console.log('Models already exist and are complete, only updating visibility');
        // 模型已存在且完整，只需更新可见性
        requestAnimationFrame(() => {
          if (moonRef.current && moonLoadedRef.current) {
            moonRef.current.visible = true;
          }
          if (roseRef.current && roseLoadedRef.current) {
            roseRef.current.visible = true;
          }
        });
      } else if (isLoadingMoonRoseRef.current) {
        console.log('Models are currently loading, waiting...');
      }
    }
    
    // 当currentModel变化时，立即更新模型可见性
    // 使用requestAnimationFrame确保在渲染循环中更新
    // 只有在模型加载完成后才更新可见性
    requestAnimationFrame(() => {
      if (moonRef.current && moonLoadedRef.current) {
        moonRef.current.visible = currentModel === 'moon-rose';
        console.log('Moon visibility updated via useEffect (RAF), visible:', moonRef.current.visible, 'currentModel:', currentModel);
      }
      if (roseRef.current && roseLoadedRef.current) {
        roseRef.current.visible = currentModel === 'moon-rose';
        console.log('Rose visibility updated via useEffect (RAF), visible:', roseRef.current.visible, 'currentModel:', currentModel);
      }
      if (princeRef.current && princeLoadedRef.current) {
        princeRef.current.visible = currentModel === 'prince';
        console.log('Prince visibility updated via useEffect (RAF), visible:', princeRef.current.visible, 'currentModel:', currentModel);
      }
      
      // 更新种植的玫瑰的可见性
      const shouldShowPlantedRoses = currentModel === 'prince';
      if (plantedRosesRef.current && plantedRosesRef.current.length > 0) {
        const scene = sceneRef.current;
        plantedRosesRef.current.forEach((rose) => {
          if (rose) {
            // 如果应该显示但不在场景中，重新添加
            if (shouldShowPlantedRoses && scene && !scene.children.includes(rose)) {
              console.log('Re-adding planted rose to scene in useEffect');
              scene.add(rose);
            }
            // 设置可见性
            rose.visible = shouldShowPlantedRoses;
            rose.traverse((child) => {
              if (child.isMesh || child.isGroup) {
                child.visible = shouldShowPlantedRoses;
              }
            });
          }
        });
        console.log('Planted roses visibility updated via useEffect (RAF), visible:', shouldShowPlantedRoses, 'currentModel:', currentModel, 'count:', plantedRosesRef.current.length);
      }
    });
  }, [currentModel]);
  
  // 同步roseClicked到ref
  useEffect(() => {
    roseClickedRef.current = roseClicked;
  }, [roseClicked]);
  
  // 同步isCarryingRose到ref
  useEffect(() => {
    isCarryingRoseRef.current = isCarryingRose;
  }, [isCarryingRose]);

  // 初始化全局函数供iframe调用
  useEffect(() => {
    if (typeof window !== 'undefined') {
      // 初始化latestUnityValue
      window.latestUnityValue = null;
      
      // 监听来自iframe的postMessage消息
      const handleMessage = (event) => {
        console.log('handleMessage', event);
        // 验证消息来源
        // if (event.origin !== UNITY_IFRAME_ORIGIN) return;
        
        // 处理 GameQuit 消息：{ from: "unity", type }
        // type=1: 中途退出游戏, type=2: 游戏结束退出游戏
        if (event.data?.from === 'unity' && !event.data?.event && typeof event.data.type === 'number') {
          const type = event.data.type;
          console.log('收到 GameQuit 消息, type =', type);
          
          if (type === 2) {
            // 游戏结束：先播放 end 视频作为转场动画
            setInventoryItems([{ id: 1, name: '玫瑰', icon: null, count: 1, description: '玫瑰' }]);
            // 隐藏 iframe，显示 end 视频
            setIsVideoLoaded(false);
            setShowEndVideo(true);
            
            // 等待 end 视频播放完成后关闭弹框
            // 视频的 onEnded 事件会处理关闭逻辑
          } else if (type === 1) {
            // 中途退出：直接关闭游戏弹框
            setShowUnityModal(false);
          }
        }
        
        // 处理 GameStart 消息：{ from: "unity", event: "GameStart" }
        // if (event.data?.from === 'unity' && event.data?.event === 'GameStart') {
        //   console.log('收到 GameStart 消息，游戏开始');
          
        //   // 如果定义了 GameStart 回调，调用它
        //   if (typeof window.GameStart === 'function') {
        //     window.GameStart();
        //   }
        // }
      };
      
      window.addEventListener('message', handleMessage);
      
      // 清理函数
      return () => {
        window.removeEventListener('message', handleMessage);
        if (typeof window !== 'undefined') {
          delete window.GameStart;
        }
      };
    }
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    // 创建相机
    const camera = new THREE.PerspectiveCamera(
      50,
      window.innerWidth / window.innerHeight,
      1,
      3000
    );
    // 使用球坐标系初始化相机位置
    const initialSpherical = cameraSphericalRef.current;
    const princeCenter = new THREE.Vector3(0, 0, 0); // 小王子在场景中心
    const moonCenter = new THREE.Vector3(0, 100, 0); // 月球在y:100
    // 初始显示小王子，所以围绕小王子
    const initialCenter = princeCenter;
    camera.position.set(
      initialCenter.x + initialSpherical.radius * Math.sin(initialSpherical.phi) * Math.cos(initialSpherical.theta),
      initialCenter.y + initialSpherical.radius * Math.cos(initialSpherical.phi),
      initialCenter.z + initialSpherical.radius * Math.sin(initialSpherical.phi) * Math.sin(initialSpherical.theta)
    );
    cameraRef.current = camera;

    // 创建场景
    const scene = new THREE.Scene();
    // 使用更淡的蓝色雾效，或者完全移除雾效以更好地显示月亮
    scene.fog = new THREE.FogExp2(0x0000ff, 0.0003);
    sceneRef.current = scene;

    // 创建粒子几何体
    const geometry = new THREE.BufferGeometry();
    const vertices = [];
    const size = 2000;

    for (let i = 0; i < 20000; i++) {
      const x = (Math.random() * size + Math.random() * size) / 2 - size / 2;
      const y = (Math.random() * size + Math.random() * size) / 2 - size / 2;
      const z = (Math.random() * size + Math.random() * size) / 2 - size / 2;

      vertices.push(x, y, z);
    }

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));

    // 创建粒子材质
    const material = new THREE.PointsMaterial({
      size: 2,
      color: 0xffffff,
    });
    materialRef.current = material;

    // 创建粒子系统
    const particles = new THREE.Points(geometry, material);
    scene.add(particles);
    particlesRef.current = particles;

    // 创建加载月球和玫瑰模型的函数
    const loadMoonAndRose = () => {
      // 如果正在加载，直接返回，防止重复加载
      if (isLoadingMoonRoseRef.current) {
        console.log('loadMoonAndRose: Already loading, skipping...');
        return;
      }
      
      // 快速检查：如果模型已经完整存在，不需要重新加载
      const moonValid = moonRef.current && moonLoadedRef.current && scene.children.includes(moonRef.current);
      let roseValid = false;
      if (roseRef.current && roseLoadedRef.current && moonRef.current?.children.includes(roseRef.current)) {
        // 检查玫瑰是否有纹理
        let hasTexture = false;
        roseRef.current.traverse((child) => {
          if (child.isMesh && child.material) {
            const mat = Array.isArray(child.material) ? child.material[0] : child.material;
            if (mat && mat.map) {
              hasTexture = true;
            }
          }
        });
        roseValid = hasTexture;
      }
      
      if (moonValid && roseValid) {
        console.log('loadMoonAndRose: Models already exist and are complete, skipping reload');
        return;
      }
      
      console.log('loadMoonAndRose called, cleaning up existing models...');
      isLoadingMoonRoseRef.current = true;
      
      // 彻底清理场景中所有月球和玫瑰实例
      // 遍历场景中的所有对象，找到所有月球和玫瑰
      // 注意：不要清理种植的玫瑰（通过 userData.isPlanted 标识）
      const objectsToRemove = [];
      scene.traverse((object) => {
        // 跳过种植的玫瑰
        if (object.userData && object.userData.isPlanted) {
          return;
        }
        
        // 检查是否是月球（通过位置和缩放判断，或者通过ref判断）
        if (object === moonRef.current || 
            (object.position.y === 100 && object.scale.x === 50 && object.scale.y === 50 && object.scale.z === 50)) {
          objectsToRemove.push({ type: 'moon', object });
        }
        // 检查是否是玫瑰（通过位置和缩放判断，或者通过ref判断）
        // 注意：种植的玫瑰 scale 是 6，不会被这个条件匹配
        if (object === roseRef.current ||
            (object.position.y === 1.0 && object.scale.x === 0.6 && object.scale.y === 0.6 && object.scale.z === 0.6 && 
             Math.abs(object.rotation.y - Math.PI / 4) < 0.1)) {
          objectsToRemove.push({ type: 'rose', object });
        }
      });
      
      // 清理找到的对象
      objectsToRemove.forEach(({ type, object }) => {
        console.log(`Removing ${type} from scene:`, object);
        // 清理资源
        object.traverse((child) => {
          if (child.isMesh) {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat && mat.map) mat.map.dispose();
                  if (mat) mat.dispose();
                });
              } else {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
              }
            }
          }
        });
        // 从父对象中移除
        if (object.parent) {
          object.parent.remove(object);
        }
        // 从场景中移除
        if (scene.children.includes(object)) {
          scene.remove(object);
        }
      });
      
      // 如果模型已存在，先清理
      if (moonRef.current) {
        // 先清理玫瑰（如果存在）
        if (roseRef.current && moonRef.current.children.includes(roseRef.current)) {
          // 清理玫瑰模型资源
          roseRef.current.traverse((child) => {
            if (child.isMesh) {
              if (child.geometry) child.geometry.dispose();
              if (child.material) {
                if (Array.isArray(child.material)) {
                  child.material.forEach((mat) => {
                    if (mat && mat.map) mat.map.dispose();
                    if (mat) mat.dispose();
                  });
                } else {
                  if (child.material.map) child.material.map.dispose();
                  child.material.dispose();
                }
              }
            }
          });
          moonRef.current.remove(roseRef.current);
          roseRef.current = null;
        }
        
        // 清理月球模型资源
        moonRef.current.traverse((child) => {
          if (child.isMesh) {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat && mat.map) mat.map.dispose();
                  if (mat) mat.dispose();
                });
              } else {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
              }
            }
          }
        });
        if (scene.children.includes(moonRef.current)) {
          scene.remove(moonRef.current);
        }
        moonRef.current = null;
      }
      
      // 如果玫瑰独立存在于场景中（不应该发生，但为了安全起见）
      if (roseRef.current) {
        if (scene.children.includes(roseRef.current)) {
          roseRef.current.traverse((child) => {
            if (child.isMesh) {
              if (child.geometry) child.geometry.dispose();
              if (child.material) {
                if (Array.isArray(child.material)) {
                  child.material.forEach((mat) => {
                    if (mat && mat.map) mat.map.dispose();
                    if (mat) mat.dispose();
                  });
                } else {
                  if (child.material.map) child.material.map.dispose();
                  child.material.dispose();
                }
              }
            }
          });
          scene.remove(roseRef.current);
        }
        roseRef.current = null;
      }
      
      // 重置加载状态
      moonLoadedRef.current = false;
      roseLoadedRef.current = false;
      
      console.log('Cleanup complete, scene children count:', scene.children.length);
      
      console.log('Force reloading moon and rose models...');
      
      // 重新加载月球模型（这里会触发后续的玫瑰加载）
      const loader = new GLTFLoader();
      const modelDir = moonModelPath.substring(0, moonModelPath.lastIndexOf('/') + 1);
      loader.setPath(modelDir);
      const modelFileName = moonModelPath.substring(moonModelPath.lastIndexOf('/') + 1);
      
      loader.load(
        modelFileName,
        (gltf) => {
          const moon = gltf.scene;
          moon.scale.set(50, 50, 50);
          moon.position.set(0, 100, 0);
          moon.traverse((child) => {
            if (child.isMesh) {
              child.castShadow = true;
              child.receiveShadow = true;
              if (child.material) {
                if (Array.isArray(child.material)) {
                  child.material.forEach((mat) => {
                    if (mat) {
                      mat.fog = false;
                      if (mat.emissive) {
                        mat.emissive.setHex(0x666666);
                      }
                      mat.emissiveIntensity = 0.5;
                    }
                  });
                } else {
                  child.material.fog = false;
                  if (child.material.emissive) {
                    child.material.emissive.setHex(0x666666);
                  }
                  child.material.emissiveIntensity = 0.5;
                }
              }
            }
          });
          // 检查是否已经有月球在场景中（防止重复添加）
          if (moonRef.current && scene.children.includes(moonRef.current)) {
            console.warn('Moon already exists in scene, removing old one before adding new');
            scene.remove(moonRef.current);
          }
          
          scene.add(moon);
          moonRef.current = moon;
          moonLoadedRef.current = true;
          
          const currentState = currentModelRef.current;
          moon.visible = currentState === 'moon-rose';
          // 清除reloading标记
          if (scene.userData) {
            scene.userData.reloadingMoonRose = false;
          }
          console.log('Moon reloaded and added to scene, visible:', moon.visible, 'currentModel:', currentState);
          
          // 重新加载玫瑰模型（包含完整的纹理加载逻辑）
          const roseLoader = new GLTFLoader();
          const roseModelDir = roseModelPath.substring(0, roseModelPath.lastIndexOf('/') + 1);
          roseLoader.setPath(roseModelDir);
          const roseFileName = roseModelPath.substring(roseModelPath.lastIndexOf('/') + 1);
          
          // 加载纹理
          const textureLoader = new TextureLoader();
          const textureBasePath = roseModelDir + 'textures/';
          let diffuseTexture = null;
          
          // 先加载纹理
          textureLoader.load(
            textureBasePath + 'Red_rose_diffuse.jpeg',
            (texture) => {
              console.log('Diffuse texture loaded successfully for reload:', texture);
              texture.flipY = false;
              texture.needsUpdate = true;
              diffuseTexture = texture;
              // 如果模型已经加载，立即应用纹理
              if (roseRef.current) {
                applyTextureToRose(roseRef.current, texture);
              }
            },
            undefined,
            (error) => {
              console.error('Error loading diffuse texture for reload:', error);
            }
          );
          
          // 辅助函数：将纹理应用到玫瑰的所有材质
          const applyTextureToRose = (rose, texture) => {
            rose.traverse((child) => {
              if (child.isMesh && child.material) {
                if (Array.isArray(child.material)) {
                  child.material.forEach((mat) => {
                    if (mat && mat.isMeshStandardMaterial && !mat.map) {
                      mat.map = texture;
                      mat.map.needsUpdate = true;
                      mat.needsUpdate = true;
                    }
                  });
                } else if (child.material.isMeshStandardMaterial && !child.material.map) {
                  child.material.map = texture;
                  child.material.map.needsUpdate = true;
                  child.material.needsUpdate = true;
                }
              }
            });
          };
          
          roseLoader.load(
            roseFileName,
            (gltf) => {
              const rose = gltf.scene;
              const scaleFactor = 0.60;
              rose.scale.set(scaleFactor, scaleFactor, scaleFactor);
              rose.position.set(0, 1.0, 0);
              rose.rotation.y = Math.PI / 4;
              rose.rotation.x = 0;
              rose.rotation.z = 0;
              
              rose.traverse((child) => {
                if (child.isMesh) {
                  child.castShadow = true;
                  child.receiveShadow = true;
                  child.visible = true;
                  child.userData.clickable = true;
                  if (child.material) {
                    if (Array.isArray(child.material)) {
                      child.material.forEach((mat) => {
                        if (mat) {
                          mat.fog = false;
                          mat.needsUpdate = true;
                          mat.visible = true;
                          if (mat.emissive) {
                            mat.emissive.setHex(0x111111);
                          }
                          mat.emissiveIntensity = 0.15;
                          
                          // 增加颜色饱和度
                          if (mat.isMeshStandardMaterial) {
                            const currentColor = mat.color || new THREE.Color(0xffffff);
                            const hsl = { h: 0, s: 0, l: 0 };
                            currentColor.getHSL(hsl);
                            hsl.s = Math.min(1.0, hsl.s * 1.3 + 0.2);
                            currentColor.setHSL(hsl.h, hsl.s, hsl.l);
                            mat.color = currentColor;
                          }
                          
                          // 应用纹理（如果已加载）
                          if (diffuseTexture && mat.isMeshStandardMaterial && !mat.map) {
                            console.log('Applying texture to material during reload, mesh:', child.name);
                            mat.map = diffuseTexture;
                            mat.map.needsUpdate = true;
                            mat.needsUpdate = true;
                          } else if (!diffuseTexture) {
                            // 如果纹理还没加载完成，等待一下再应用
                            setTimeout(() => {
                              if (diffuseTexture && !mat.map) {
                                console.log('Applying texture to material (delayed) during reload, mesh:', child.name);
                                mat.map = diffuseTexture;
                                mat.map.needsUpdate = true;
                                mat.needsUpdate = true;
                              }
                            }, 200);
                          }
                        }
                      });
                    } else {
                      child.material.fog = false;
                      child.material.needsUpdate = true;
                      child.material.visible = true;
                      if (child.material.emissive) {
                        child.material.emissive.setHex(0x111111);
                      }
                      child.material.emissiveIntensity = 0.15;
                      
                      // 增加颜色饱和度
                      if (child.material.isMeshStandardMaterial) {
                        const currentColor = child.material.color || new THREE.Color(0xffffff);
                        const hsl = { h: 0, s: 0, l: 0 };
                        currentColor.getHSL(hsl);
                        hsl.s = Math.min(1.0, hsl.s * 1.3 + 0.2);
                        currentColor.setHSL(hsl.h, hsl.s, hsl.l);
                        child.material.color = currentColor;
                      }
                      
                      // 应用纹理（如果已加载）
                      if (diffuseTexture && child.material.isMeshStandardMaterial && !child.material.map) {
                        console.log('Applying texture to material during reload, mesh:', child.name);
                        child.material.map = diffuseTexture;
                        child.material.map.needsUpdate = true;
                        child.material.needsUpdate = true;
                      } else if (!diffuseTexture) {
                        // 如果纹理还没加载完成，等待一下再应用
                        setTimeout(() => {
                          if (diffuseTexture && !child.material.map) {
                            console.log('Applying texture to material (delayed) during reload, mesh:', child.name);
                            child.material.map = diffuseTexture;
                            child.material.map.needsUpdate = true;
                            child.material.needsUpdate = true;
                          }
                        }, 200);
                      }
                    }
                  }
                }
              });
              
              // 确保没有重复添加玫瑰
              if (!moon.children.some(child => child === rose)) {
                moon.add(rose);
              }
              roseRef.current = rose;
              roseLoadedRef.current = true;
              
              // 如果纹理已经加载，立即应用
              if (diffuseTexture) {
                applyTextureToRose(rose, diffuseTexture);
              }
              
              const currentState = currentModelRef.current;
              rose.visible = currentState === 'moon-rose';
              moon.visible = currentState === 'moon-rose';
              console.log('Rose reloaded and added to moon, visible:', rose.visible, 'currentModel:', currentState);
              console.log('Moon children count after adding rose:', moon.children.length);
              
              // 加载完成，释放锁
              isLoadingMoonRoseRef.current = false;
            },
            undefined,
            (error) => {
              console.error('Error reloading rose model:', error);
              // 加载失败，释放锁
              isLoadingMoonRoseRef.current = false;
            }
          );
        },
        undefined,
        (error) => {
          console.error('Error reloading moon model:', error);
          // 加载失败，释放锁
          isLoadingMoonRoseRef.current = false;
        }
      );
    };
    
    // 将加载函数存储到ref中，以便在切换时调用
    loadMoonRoseRef.current = loadMoonAndRose;

    // 只在初始状态不是 moon-rose 时才加载月球模型（避免重复加载）
    // 如果初始状态是 moon-rose，则通过 loadMoonAndRose 函数加载
    // 同时检查是否正在加载，避免重复加载
    if (currentModelRef.current !== 'moon-rose' && !isLoadingMoonRoseRef.current) {
      // 设置加载锁
      isLoadingMoonRoseRef.current = true;
      
      // 加载 GLTF 月球模型
      const loader = new GLTFLoader();
      // 设置纹理路径的基础目录
      // 从 moonModelPath 中提取目录路径（去掉文件名，保留目录）
      const modelDir = moonModelPath.substring(0, moonModelPath.lastIndexOf('/') + 1);
      loader.setPath(modelDir);
      
      // 只使用文件名加载，因为已经设置了路径
      const modelFileName = moonModelPath.substring(moonModelPath.lastIndexOf('/') + 1);
      loader.load(
        modelFileName,
        (gltf) => {
        const moon = gltf.scene;
        // 调整月球大小和位置
        moon.scale.set(50, 50, 50); // 根据需要调整缩放
        moon.position.set(0, 100, 0);
        // 启用阴影并调整材质渲染
        moon.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            // 确保材质正确渲染，不受雾效影响太大，并增强亮度
            if (child.material) {
              // 如果是数组材质
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat) {
                    mat.fog = false; // 禁用雾效对月亮的影响
                    // 增加材质的自发光，让月亮更亮
                    if (mat.emissive) {
                      mat.emissive.setHex(0x666666); // 增加自发光亮度
                    }
                    mat.emissiveIntensity = 0.5; // 增加自发光强度
                  }
                });
              } else {
                child.material.fog = false; // 禁用雾效对月亮的影响
                // 增加材质的自发光，让月亮更亮
                if (child.material.emissive) {
                  child.material.emissive.setHex(0x666666); // 增加自发光亮度
                }
                child.material.emissiveIntensity = 0.5; // 增加自发光强度
              }
            }
          }
        });
        scene.add(moon);
        moonRef.current = moon;
        moonLoadedRef.current = true;
        
        // 模型加载完成后，立即根据当前状态更新可见性
        // 渲染循环会根据currentModel自动更新可见性，完全依赖渲染循环
        const currentState = currentModelRef.current;
        moon.visible = currentState === 'moon-rose';
        console.log('Moon loaded and added to scene, visible:', moon.visible, 'currentModel:', currentState);
        
        // 加载玫瑰模型并添加到月球上
        const roseLoader = new GLTFLoader();
        // 设置纹理路径的基础目录
        const roseModelDir = roseModelPath.substring(0, roseModelPath.lastIndexOf('/') + 1);
        roseLoader.setPath(roseModelDir);
        const roseFileName = roseModelPath.substring(roseModelPath.lastIndexOf('/') + 1);
        
        console.log('Loading rose from:', roseModelDir + roseFileName);
        console.log('Full rose path:', roseModelPath);
        console.log('Rose model directory:', roseModelDir);
        console.log('Rose file name:', roseFileName);
        
        // 由于GLTF加载器不支持KHR_materials_pbrSpecularGlossiness扩展，
        // 需要手动加载纹理并应用
        const textureLoader = new TextureLoader();
        const textureBasePath = roseModelDir + 'textures/';
        let diffuseTexture = null;
        
        // 先加载纹理
        textureLoader.load(
          textureBasePath + 'Red_rose_diffuse.jpeg',
          (texture) => {
            console.log('Diffuse texture loaded successfully:', texture);
            // 设置纹理参数，确保正确显示
            texture.flipY = false; // GLTF纹理通常不需要翻转
            texture.needsUpdate = true;
            diffuseTexture = texture;
            // 如果模型已经加载，立即应用纹理
            if (roseRef.current) {
              applyTextureToRose(roseRef.current, texture);
            }
          },
          undefined,
          (error) => {
            console.error('Error loading diffuse texture:', error);
          }
        );
        
        // 辅助函数：将纹理应用到玫瑰的所有材质
        const applyTextureToRose = (rose, texture) => {
          rose.traverse((child) => {
            if (child.isMesh && child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat && mat.isMeshStandardMaterial && !mat.map) {
                    // 使用同一个纹理实例，不要克隆，确保所有mesh共享同一个纹理
                    mat.map = texture;
                    mat.map.needsUpdate = true;
                    mat.needsUpdate = true;
                  }
                });
              } else if (child.material.isMeshStandardMaterial && !child.material.map) {
                // 使用同一个纹理实例，不要克隆，确保所有mesh共享同一个纹理
                child.material.map = texture;
                child.material.map.needsUpdate = true;
                child.material.needsUpdate = true;
              }
            }
          });
        };
        
        // 使用文件名加载（因为已经设置了路径）
        roseLoader.load(
          roseFileName,
          (gltf) => {
            console.log('Rose model loaded successfully!', gltf);
            const rose = gltf.scene;
            
            // 计算玫瑰的边界框以了解其大小
            const box = new THREE.Box3().setFromObject(rose);
            const size = box.getSize(new THREE.Vector3());
            const center = box.getCenter(new THREE.Vector3());
            console.log('Rose bounding box size:', size);
            console.log('Rose bounding box center:', center);
            
            // 调整玫瑰大小（相对于月球，月球scale是50）
            // 将玫瑰缩小到原来的10%（再次缩小）
            const scaleFactor = 0.60; // 缩放因子（1.5的10%）
            rose.scale.set(scaleFactor, scaleFactor, scaleFactor);
            
            // 将玫瑰放置在月球表面上方（相对于月球的局部坐标）
            // 月球scale是50，所以局部坐标会被放大50倍
            // 如果想让玫瑰在世界坐标 y: 150 左右（月球在 y: 100，玫瑰在其上方50单位）
            // 那么局部坐标应该是 (150 - 100) / 50 = 1.0
            // 但考虑到玫瑰本身有高度，需要稍微调整
            // 玫瑰边界框中心在 y: 1.29，缩放15倍后中心在 y: 19.35
            // 所以局部位置应该考虑这个偏移
            const localY = 1.0; // 局部坐标1，放大50倍后是世界坐标50，加上月球位置100 = 150
            rose.position.set(0, localY, 0);
            
            // 调整玫瑰的旋转，使其看起来更自然
            // 只旋转Y轴（水平旋转），不旋转X轴和Z轴，避免倾倒
            rose.rotation.y = Math.PI / 4;
            rose.rotation.x = 0; // 不倾斜，保持垂直
            rose.rotation.z = 0; // 不旋转Z轴
            
            // 设置玫瑰的材质属性
            // 注意：模型使用了 KHR_materials_pbrSpecularGlossiness 扩展
            // Three.js 可能不支持，但会回退到标准材质
            // 保持原始纹理，只禁用雾效以确保可见
            // 不要手动覆盖纹理，让GLTF加载器自己处理纹理映射
            rose.traverse((child) => {
              if (child.isMesh) {
                child.castShadow = true;
                child.receiveShadow = true;
                child.visible = true; // 确保可见
                // 给玫瑰的所有mesh添加可点击标识
                child.userData.clickable = true;
                if (child.material) {
                  if (Array.isArray(child.material)) {
                    child.material.forEach((mat, index) => {
                      if (mat) {
                        mat.fog = false; // 禁用雾效，保持原始材质和纹理
                        mat.needsUpdate = true;
                        mat.visible = true;
                        // 添加轻微自发光，让玫瑰更亮
                        if (mat.emissive) {
                          mat.emissive.setHex(0x111111); // 轻微自发光
                        }
                        mat.emissiveIntensity = 0.15; // 轻微自发光强度
                        
                        // 增加颜色饱和度，让玫瑰更鲜艳
                        if (mat.isMeshStandardMaterial) {
                          // 使用HSL颜色空间来增加饱和度
                          // 将颜色转换为HSL，增加饱和度，再转回RGB
                          const currentColor = mat.color || new THREE.Color(0xffffff);
                          const hsl = { h: 0, s: 0, l: 0 };
                          currentColor.getHSL(hsl);
                          // 增加饱和度（限制在0-1之间）
                          hsl.s = Math.min(1.0, hsl.s * 1.3 + 0.2); // 增加饱和度
                          currentColor.setHSL(hsl.h, hsl.s, hsl.l);
                          mat.color = currentColor;
                        }
                        
                        // 调试：检查纹理是否正确加载
                        console.log(`Rose material ${index} (mesh: ${child.name}):`, {
                          type: mat.type,
                          map: mat.map ? 'has map' : 'no map',
                          mapUrl: mat.map ? mat.map.image?.src : null,
                          normalMap: mat.normalMap ? 'has normalMap' : 'no normalMap',
                          aoMap: mat.aoMap ? 'has aoMap' : 'no aoMap',
                          name: mat.name || 'unnamed'
                        });
                        
                        // 由于GLTF加载器不支持KHR_materials_pbrSpecularGlossiness扩展，
                        // 需要手动应用纹理
                        if (!mat.map && mat.isMeshStandardMaterial) {
                          if (diffuseTexture) {
                            console.log(`Applying texture to material ${index}, mesh: ${child.name}`);
                            // 使用同一个纹理实例，不要克隆，确保所有mesh共享同一个纹理
                            // 这样UV映射才能正确工作
                            mat.map = diffuseTexture;
                            mat.map.needsUpdate = true;
                            mat.needsUpdate = true;
                          } else {
                            // 如果纹理还没加载完成，等待一下再应用
                            setTimeout(() => {
                              if (diffuseTexture && !mat.map) {
                                console.log(`Applying texture to material ${index} (delayed), mesh: ${child.name}`);
                                mat.map = diffuseTexture;
                                mat.map.needsUpdate = true;
                                mat.needsUpdate = true;
                              }
                            }, 200);
                          }
                        }
                      }
                    });
                  } else {
                    child.material.fog = false; // 禁用雾效，保持原始材质和纹理
                    child.material.needsUpdate = true;
                    child.material.visible = true;
                    // 添加轻微自发光，让玫瑰更亮
                    if (child.material.emissive) {
                      child.material.emissive.setHex(0x111111); // 轻微自发光
                    }
                    child.material.emissiveIntensity = 0.15; // 轻微自发光强度
                    
                    // 增加颜色饱和度，让玫瑰更鲜艳
                    if (child.material.isMeshStandardMaterial) {
                      // 使用HSL颜色空间来增加饱和度
                      // 将颜色转换为HSL，增加饱和度，再转回RGB
                      const currentColor = child.material.color || new THREE.Color(0xffffff);
                      const hsl = { h: 0, s: 0, l: 0 };
                      currentColor.getHSL(hsl);
                      // 增加饱和度（限制在0-1之间）
                      hsl.s = Math.min(1.0, hsl.s * 1.3 + 0.2); // 增加饱和度
                      currentColor.setHSL(hsl.h, hsl.s, hsl.l);
                      child.material.color = currentColor;
                    }
                    
                    // 调试：检查纹理是否正确加载
                    console.log(`Rose material (mesh: ${child.name}):`, {
                      type: child.material.type,
                      map: child.material.map ? 'has map' : 'no map',
                      mapUrl: child.material.map ? child.material.map.image?.src : null,
                      normalMap: child.material.normalMap ? 'has normalMap' : 'no normalMap',
                      aoMap: child.material.aoMap ? 'has aoMap' : 'no aoMap',
                      name: child.material.name || 'unnamed'
                    });
                    
                    // 由于GLTF加载器不支持KHR_materials_pbrSpecularGlossiness扩展，
                    // 需要手动应用纹理
                    if (!child.material.map && child.material.isMeshStandardMaterial) {
                      if (diffuseTexture) {
                        console.log(`Applying texture to material, mesh: ${child.name}`);
                        // 使用同一个纹理实例，不要克隆，确保所有mesh共享同一个纹理
                        // 这样UV映射才能正确工作
                        child.material.map = diffuseTexture;
                        child.material.map.needsUpdate = true;
                        child.material.needsUpdate = true;
                      } else {
                        // 如果纹理还没加载完成，等待一下再应用
                        setTimeout(() => {
                          if (diffuseTexture && !child.material.map) {
                            console.log(`Applying texture to material (delayed), mesh: ${child.name}`);
                            child.material.map = diffuseTexture;
                            child.material.map.needsUpdate = true;
                            child.material.needsUpdate = true;
                          }
                        }, 200);
                      }
                    }
                  }
                }
              }
            });
            
            // 将玫瑰添加到月球作为子对象，这样它会跟随月球旋转和移动
            // 确保没有重复添加玫瑰
            if (!moon.children.some(child => child === rose)) {
              moon.add(rose);
            }
            roseRef.current = rose;
            roseLoadedRef.current = true;
            
            // 模型加载完成后，立即根据当前状态更新可见性
            // 渲染循环会根据currentModel自动更新可见性，完全依赖渲染循环
            const currentState = currentModelRef.current;
            rose.visible = currentState === 'moon-rose';
            moon.visible = currentState === 'moon-rose';
            console.log('Rose loaded and added to moon, visible:', rose.visible, 'currentModel:', currentState);
            console.log('Moon has children:', moon.children.length);
            
            // 初始加载完成，释放锁
            isLoadingMoonRoseRef.current = false;
            
            // 计算世界坐标位置
            const worldPosition = new THREE.Vector3();
            rose.getWorldPosition(worldPosition);
            console.log('Rose added to moon at local position:', rose.position);
            console.log('Rose world position:', worldPosition);
            console.log('Moon position:', moon.position);
            console.log('Rose scale:', rose.scale);
            
            // 加载小王子模型
            const princeLoader = new GLTFLoader();
            const princeModelDir = princeModelPath.substring(0, princeModelPath.lastIndexOf('/') + 1);
            princeLoader.setPath(princeModelDir);
            const princeFileName = princeModelPath.substring(princeModelPath.lastIndexOf('/') + 1);
            
            console.log('Loading prince from:', princeModelDir + princeFileName);
            
            princeLoader.load(
              princeFileName,
              (gltf) => {
                console.log('Prince model loaded successfully!', gltf);
                const prince = gltf.scene;
                
                // 计算小王子的边界框以了解其大小
                const box = new THREE.Box3().setFromObject(prince);
                const size = box.getSize(new THREE.Vector3());
                const center = box.getCenter(new THREE.Vector3());
                console.log('Prince bounding box size:', size);
                console.log('Prince bounding box center:', center);
                
                // 调整小王子大小（相对于月球，月球scale是50）
                // 根据小王子的大小调整缩放，使其与玫瑰大小相当
                const scaleFactor = 0.6; // 可以根据需要调整
                prince.scale.set(scaleFactor, scaleFactor, scaleFactor);
                
                // 将小王子放置在月球表面上方（相对于月球的局部坐标）
                // 与玫瑰使用相同的位置
                const localY = 1.0; // 局部坐标，会被月球scale放大
                prince.position.set(0, localY, 0);
                
                // 调整小王子的旋转
                prince.rotation.y = 0;
                prince.rotation.x = 0;
                prince.rotation.z = 0;
                
                // 设置小王子的材质属性
                prince.traverse((child) => {
                  if (child.isMesh) {
                    child.castShadow = true;
                    child.receiveShadow = true;
                    child.visible = true;
                    if (child.material) {
                      if (Array.isArray(child.material)) {
                        child.material.forEach((mat) => {
                          if (mat) {
                            mat.fog = false;
                            mat.needsUpdate = true;
                            mat.visible = true;
                            // 添加轻微自发光，让小王子更亮
                            if (mat.emissive) {
                              mat.emissive.setHex(0x111111);
                            }
                            mat.emissiveIntensity = 0.15;
                          }
                        });
                      } else {
                        child.material.fog = false;
                        child.material.needsUpdate = true;
                        child.material.visible = true;
                        // 添加轻微自发光，让小王子更亮
                        if (child.material.emissive) {
                          child.material.emissive.setHex(0x111111);
                        }
                        child.material.emissiveIntensity = 0.15;
                      }
                    }
                  }
                });
                
                // 确保小王子本身可见
                prince.visible = true;
                
                // 将小王子添加到月球作为子对象（但这里我们不会这样做，因为小王子是独立加载的）
                // moon.add(prince);
                // princeRef.current = prince;
                
                // 注意：这里的小王子加载代码是旧的，现在小王子是独立加载的，所以这部分代码不会执行
                console.log('Old prince loading code (not used)');
              },
              (progress) => {
                if (progress.lengthComputable) {
                  const percent = (progress.loaded / progress.total * 100).toFixed(2);
                  console.log('Loading prince model:', percent + '%');
                }
              },
              (error) => {
                console.error('Error loading prince model:', error);
                console.error('Attempted path:', princeModelPath);
              }
            );
          },
          (progress) => {
            if (progress.lengthComputable) {
              const percent = (progress.loaded / progress.total * 100).toFixed(2);
              console.log('Loading rose model:', percent + '%');
            } else {
              console.log('Loading rose model, loaded:', progress.loaded);
            }
          },
          (error) => {
            console.error('Error loading rose model:', error);
            console.error('Error details:', error.message);
            console.error('Attempted path:', roseModelPath);
            console.error('Attempted directory:', roseModelDir);
          }
        );
      },
      (progress) => {
        // 加载进度回调
        if (progress.lengthComputable) {
          console.log('Loading moon model:', (progress.loaded / progress.total * 100) + '%');
        }
      },
      (error) => {
        console.error('Error loading moon model:', error);
        console.error('Attempted path:', moonModelPath);
        // 加载失败，释放锁
        isLoadingMoonRoseRef.current = false;
      }
    );
    } // 结束 if (currentModelRef.current !== 'moon-rose')
    
    // 加载小王子模型作为主模型
    const princeLoader = new GLTFLoader();
    const princeModelDir = princeModelPath.substring(0, princeModelPath.lastIndexOf('/') + 1);
    princeLoader.setPath(princeModelDir);
    const princeFileName = princeModelPath.substring(princeModelPath.lastIndexOf('/') + 1);
    
    console.log('Loading prince from:', princeModelDir + princeFileName);
    
    princeLoader.load(
      princeFileName,
      (gltf) => {
        console.log('Prince model loaded successfully!', gltf);
        const prince = gltf.scene;
        
        // 计算小王子的边界框以了解其大小
        const box = new THREE.Box3().setFromObject(prince);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        console.log('Prince bounding box size:', size);
        console.log('Prince bounding box center:', center);
        
        // 调整小王子大小，使其成为主模型（根据模型大小调整缩放）
        const scaleFactor = 10; // 可以根据需要调整，使小王子大小合适
        prince.scale.set(scaleFactor, scaleFactor, scaleFactor);
        
        // 将小王子放置在场景中心
        prince.position.set(0, 0, 0);
        
        // 调整小王子的旋转
        prince.rotation.y = 0;
        prince.rotation.x = 0;
        prince.rotation.z = 0;
        
        // 设置小王子的材质属性
        let meshIndex = 0;
        prince.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;
            child.visible = true;
            
            // 打印mesh信息，方便调试
            console.log(`Mesh ${meshIndex}: name="${child.name}", type=${child.type}`);
            
            // 给第一个mesh或者特定名称的mesh添加可点击标识
            // 你可以根据需要修改这个条件来选择要点击的节点
            // 例如：child.name.includes('head') 或 meshIndex === 0
            if (!child.userData.hasOwnProperty('clickable')) {
              // 默认第一个mesh可点击，你可以根据需要修改
              // 方式1：第一个mesh可点击
              child.userData.clickable = meshIndex === 0;
              // 方式2：根据名称判断（取消注释下面这行，注释掉上面这行）
              // child.userData.clickable = child.name && (child.name.includes('head') || child.name.includes('body') || child.name.includes('Head') || child.name.includes('Body'));
              // 方式3：所有mesh都可点击（取消注释下面这行，注释掉上面这行）
              // child.userData.clickable = true;
            }
            meshIndex++;
            
            if (child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat) {
                    mat.fog = false;
                    mat.needsUpdate = true;
                    mat.visible = true;
                    // 添加轻微自发光，让小王子更亮
                    if (mat.emissive) {
                      mat.emissive.setHex(0x111111);
                    }
                    mat.emissiveIntensity = 0.15;
                  }
                });
              } else {
                child.material.fog = false;
                child.material.needsUpdate = true;
                child.material.visible = true;
                // 添加轻微自发光，让小王子更亮
                if (child.material.emissive) {
                  child.material.emissive.setHex(0x111111);
                }
                child.material.emissiveIntensity = 0.15;
              }
            }
          }
        });
        
        // 确保小王子本身可见
        prince.visible = true;
        
        // 将小王子直接添加到场景（不再作为月球的子对象）
        scene.add(prince);
        princeRef.current = prince;
        princeLoadedRef.current = true;
        
        console.log('Prince added to scene at position:', prince.position);
      },
      (progress) => {
        if (progress.lengthComputable) {
          const percent = (progress.loaded / progress.total * 100).toFixed(2);
          console.log('Loading prince model:', percent + '%');
        }
      },
      (error) => {
        console.error('Error loading prince model:', error);
        console.error('Attempted path:', princeModelPath);
      }
    );

    // 添加环境光（增强亮度以更好地显示纹理）
    const ambientLight = new THREE.AmbientLight(0xffffff, 2.5); // 从1.5增加到2.5
    scene.add(ambientLight);

    // 添加点光源（模拟太阳光照射月球）
    const pointLight = new THREE.PointLight(0xffffff, 4.0, 1000); // 从2.5增加到4.0
    pointLight.position.set(300, 200, 400);
    scene.add(pointLight);
    
    // 添加额外的定向光源，从正面照射月亮
    const directionalLight = new THREE.DirectionalLight(0xffffff, 2.5); // 从1.5增加到2.5
    directionalLight.position.set(0, 100, 500);
    scene.add(directionalLight);

    // 创建渲染器
    const renderer = new THREE.WebGLRenderer();
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 创建射线检测器
    const raycaster = new THREE.Raycaster();
    raycasterRef.current = raycaster;
    
    // 更新跟随鼠标的玫瑰位置
    const updateCursorRosePosition = (mouseX, mouseY) => {
      if (!cursorRoseRef.current || !camera || !renderer) {
        console.warn('Cannot update cursor rose: missing refs', {
          cursorRose: !!cursorRoseRef.current,
          camera: !!camera,
          renderer: !!renderer
        });
        return;
      }
      
      // 将鼠标坐标转换为标准化设备坐标（NDC）
      const mouse = new THREE.Vector2();
      mouse.x = (mouseX / window.innerWidth) * 2 - 1;
      mouse.y = -(mouseY / window.innerHeight) * 2 + 1;
      
      // 使用射线检测器计算3D位置
      const tempRaycaster = new THREE.Raycaster();
      tempRaycaster.setFromCamera(mouse, camera);
      
      // 在相机前方一定距离处放置玫瑰（跟随鼠标的深度）
      // 使用相对于相机距离的比例，这样滚轮缩放时玫瑰也会跟随
      // 计算当前相机到场景中心的距离
      const sceneCenter = new THREE.Vector3(0, 0, 0);
      const cameraDistance = camera.position.distanceTo(sceneCenter);
      // 使用相机距离的5-10%作为玫瑰距离，确保玫瑰始终在视野内
      const distanceRatio = 0.08; // 相机距离的8%
      const distance = Math.max(10, cameraDistance * distanceRatio); // 最小距离10
      const direction = tempRaycaster.ray.direction.clone();
      const position = new THREE.Vector3();
      position.copy(camera.position);
      position.add(direction.multiplyScalar(distance));
      
      cursorRoseRef.current.position.copy(position);
      
      // 确保玫瑰可见
      cursorRoseRef.current.visible = true;
      
      // 让玫瑰始终面向相机
      cursorRoseRef.current.lookAt(camera.position);
      // 旋转180度，让玫瑰看起来更自然
      cursorRoseRef.current.rotateY(Math.PI);
      
      // 调试信息（每100次更新打印一次）
      if (!updateCursorRosePosition.debugCount) {
        updateCursorRosePosition.debugCount = 0;
      }
      updateCursorRosePosition.debugCount++;
      if (updateCursorRosePosition.debugCount % 100 === 0) {
        console.log('Cursor rose updated:', {
          mouse: { x: mouseX, y: mouseY },
          position: position,
          camera: camera.position
        });
      }
    };
    
    // 将函数保存到ref中，以便在其他地方使用
    updateCursorRosePositionRef.current = updateCursorRosePosition;

    // 鼠标拖动开始
    const handlePointerDown = (event) => {
      // 只响应主按钮（左键）的拖动
      if (event.button !== 0) return;
      
      // 如果用户开始拖动，取消视角恢复操作
      if (isRestoringViewRef.current) {
        isRestoringViewRef.current = false;
        console.log('User started dragging, canceling view restoration');
      }
      
      // 记录拖动开始位置，用于区分点击和拖动
      dragStartXRef.current = event.clientX;
      dragStartYRef.current = event.clientY;
      
      isDraggingRef.current = true;
      lastMouseXRef.current = event.clientX;
      lastMouseYRef.current = event.clientY;
      containerRef.current.style.cursor = 'grabbing';
      event.preventDefault(); // 防止默认行为
    };
    
    // 鼠标移动（用于更新跟随鼠标的玫瑰位置）
    const handleMouseMove = (event) => {
      // 更新鼠标位置状态
      setMousePosition({ x: event.clientX, y: event.clientY });
      
      // 如果正在携带玫瑰，立即更新玫瑰位置（不等待状态更新）
      if (isCarryingRoseRef.current && cursorRoseRef.current && updateCursorRosePositionRef.current) {
        updateCursorRosePositionRef.current(event.clientX, event.clientY);
      } else if (isCarryingRoseRef.current) {
        // 调试：如果应该更新但没有更新
        if (!cursorRoseRef.current) {
          console.warn('handleMouseMove: cursorRoseRef.current is null');
        }
        if (!updateCursorRosePositionRef.current) {
          console.warn('handleMouseMove: updateCursorRosePositionRef.current is null');
        }
      }
    };
    
    // 鼠标拖动中
    const handlePointerMove = (event) => {
      // 更新鼠标位置（即使不在拖动状态）
      handleMouseMove(event);
      
      if (!isDraggingRef.current) return;
      
      // 计算鼠标移动的差值
      const deltaX = event.clientX - lastMouseXRef.current;
      const deltaY = event.clientY - lastMouseYRef.current;
      
      // 如果移动距离太小，忽略（避免微小抖动）
      if (Math.abs(deltaX) < 0.1 && Math.abs(deltaY) < 0.1) return;
      
      // 使用球坐标系：根据鼠标移动更新角度
      const sensitivity = 0.005; // 角度灵敏度
      targetSphericalRef.current.theta += deltaX * sensitivity; // 水平旋转
      
      // 根据当前模型决定是否允许垂直旋转
      const currentModelValue = currentModelRef.current;
      if (currentModelValue === 'moon-rose') {
        // 显示月球+玫瑰时，允许360度无死角旋转（包括垂直旋转）
        targetSphericalRef.current.phi -= deltaY * sensitivity; // 垂直旋转
        
        // 限制phi角度范围，避免相机翻转（0到π之间）
        const minPhi = 0.1; // 接近顶部但不完全垂直向上
        const maxPhi = Math.PI - 0.1; // 接近底部但不完全垂直向下
        targetSphericalRef.current.phi = Math.max(minPhi, Math.min(maxPhi, targetSphericalRef.current.phi));
      } else {
        // 显示小王子时，固定垂直角度，只允许水平旋转
        targetSphericalRef.current.phi = Math.PI / 2;
      }
      
      // 更新上一次鼠标位置
      lastMouseXRef.current = event.clientX;
      lastMouseYRef.current = event.clientY;
      
      event.preventDefault(); // 防止默认行为
    };
    
    // 鼠标拖动结束
    const handlePointerUp = (event) => {
      if (event.button !== 0) return;
      
      // 计算移动距离，判断是点击还是拖动
      const deltaX = Math.abs(event.clientX - dragStartXRef.current);
      const deltaY = Math.abs(event.clientY - dragStartYRef.current);
      const moveDistance = Math.sqrt(deltaX * deltaX + deltaY * deltaY);
      
      // 如果移动距离很小（小于5像素），认为是点击，执行射线检测
      if (moveDistance < 5 && raycasterRef.current && cameraRef.current && rendererRef.current) {
        // 将鼠标坐标转换为标准化设备坐标（NDC）
        const mouse = new THREE.Vector2();
        mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;
        
        // 更新射线检测器
        raycasterRef.current.setFromCamera(mouse, cameraRef.current);
        
        const currentModelValue = currentModelRef.current;
        
        // 如果当前显示的是小王子，先检测是否点击到种植的玫瑰
        if (currentModelValue === 'prince' && plantedRosesRef.current && plantedRosesRef.current.length > 0) {
          // 检测所有种植的玫瑰
          for (const plantedRose of plantedRosesRef.current) {
            if (plantedRose && sceneRef.current && sceneRef.current.children.includes(plantedRose)) {
              const intersects = raycasterRef.current.intersectObject(plantedRose, true);
              
              if (intersects.length > 0) {
                const clickedMesh = intersects[0].object;
                
                // 检查点击的mesh是否属于种植的玫瑰（通过向上查找父对象）
                let currentObject = clickedMesh;
                let isPlantedRose = false;
                while (currentObject) {
                  if (currentObject.userData && currentObject.userData.isPlanted) {
                    isPlantedRose = true;
                    break;
                  }
                  currentObject = currentObject.parent;
                }
                
                // 如果点击到种植的玫瑰
                if (isPlantedRose && clickedMesh.userData.clickable) {
                  console.log('Clicked on planted rose:', clickedMesh.name || 'unnamed');
                  
                  // 触发切换到月球玫瑰的逻辑
                  // 先恢复视角到初始值，等恢复完成后再切换模型
                  const initialView = princeInitialViewRef.current;
                  
                  // 设置目标视角为初始值
                  targetSphericalRef.current.radius = initialView.radius;
                  targetSphericalRef.current.theta = initialView.theta;
                  targetSphericalRef.current.phi = initialView.phi;
                  
                  // 标记正在恢复视角
                  isRestoringViewRef.current = true;
                  
                  console.log('Restoring view to initial position before switching to moon-rose');
                  
                  // 停止后续的小王子点击检测
                  return;
                }
              }
            }
          }
        }
        
        // 如果当前显示的是小王子，检测点击小王子
        if (currentModelValue === 'prince' && princeRef.current) {
          const intersects = raycasterRef.current.intersectObject(princeRef.current, true);
          
          if (intersects.length > 0) {
            const clickedMesh = intersects[0].object;
            const intersectPoint = intersects[0].point; // 获取点击的交点位置
            // 获取法线：优先使用 face.normal，如果没有则计算
            let intersectNormal = null;
            if (intersects[0].face) {
              // 将局部法线转换为世界坐标
              intersectNormal = intersects[0].face.normal.clone();
              intersectNormal.applyMatrix4(clickedMesh.matrixWorld);
              intersectNormal.normalize();
            } else {
              // 如果没有法线，计算从点击位置到模型中心的向量作为法线
              const princeBox = new THREE.Box3().setFromObject(princeRef.current);
              const princeCenter = princeBox.getCenter(new THREE.Vector3());
              intersectNormal = intersectPoint.clone().sub(princeCenter).normalize();
            }
            
            console.log('Clicked on prince mesh:', clickedMesh.name || 'unnamed', 'isCarryingRose:', isCarryingRoseRef.current);
            console.log('Intersect point:', intersectPoint);
            
            // 如果正在携带玫瑰，将玫瑰种植到小王子身上
            // 不需要检查 clickable，只要点击到小王子就可以种植
            if (isCarryingRoseRef.current && cursorRoseRef.current) {
              console.log('Planting rose on prince at click position');
              
              // 克隆跟随鼠标的玫瑰模型
              // 使用 clone(true) 进行深拷贝，但材质需要单独处理
              const plantedRose = cursorRoseRef.current.clone(true);
              
              // 确保克隆的玫瑰的材质也被正确复制，包括纹理
              // 需要重新加载纹理，因为克隆的材质可能共享纹理引用
              const textureLoader = new THREE.TextureLoader();
              const roseModelDir = roseModelPath.substring(0, roseModelPath.lastIndexOf('/') + 1);
              const textureBasePath = roseModelDir + 'textures/';
              
              // 加载纹理用于种植的玫瑰
              const plantedRoseTexture = textureLoader.load(
                textureBasePath + 'Red_rose_diffuse.jpeg',
                (texture) => {
                  texture.flipY = false;
                  texture.needsUpdate = true;
                  
                  // 纹理加载完成后，应用到所有材质
                  plantedRose.traverse((child) => {
                    if (child.isMesh && child.material) {
                      if (Array.isArray(child.material)) {
                        child.material.forEach(mat => {
                          if (mat) {
                            mat.map = texture;
                            mat.map.needsUpdate = true;
                            mat.needsUpdate = true;
                          }
                        });
                      } else {
                        child.material.map = texture;
                        child.material.map.needsUpdate = true;
                        child.material.needsUpdate = true;
                      }
                    }
                  });
                }
              );
              
              // 确保克隆的玫瑰的材质也被正确复制
              plantedRose.traverse((child) => {
                if (child.isMesh) {
                  // 确保mesh可见
                  child.visible = true;
                  // 给种植的玫瑰添加可点击标识
                  child.userData.clickable = true;
                  
                  if (child.material) {
                    // 如果材质是数组，需要克隆每个材质
                    if (Array.isArray(child.material)) {
                      child.material = child.material.map(mat => {
                        if (mat) {
                          const clonedMat = mat.clone();
                          clonedMat.visible = true;
                          clonedMat.needsUpdate = true;
                          // 暂时使用原纹理，等新纹理加载完成后再替换
                          if (mat.map) {
                            clonedMat.map = mat.map;
                            clonedMat.map.needsUpdate = true;
                          }
                          return clonedMat;
                        }
                        return mat;
                      });
                    } else {
                      child.material = child.material.clone();
                      child.material.visible = true;
                      child.material.needsUpdate = true;
                      // 暂时使用原纹理，等新纹理加载完成后再替换
                      if (child.material.map) {
                        child.material.map = child.material.map;
                        child.material.map.needsUpdate = true;
                      }
                    }
                  }
                  
                  // 设置高渲染顺序
                  child.renderOrder = 998;
                }
              });
              
              // 使用点击的交点位置作为种植位置（自定义位置）
              // 如果需要稍微偏移，可以沿着法线方向移动
              const plantPosition = intersectPoint.clone();
              if (intersectNormal) {
                // 沿着法线方向稍微偏移，让玫瑰稍微离开表面
                const offset = 0.5; // 偏移距离
                plantPosition.add(intersectNormal.clone().multiplyScalar(offset));
              } else {
                // 如果没有法线，向上偏移
                plantPosition.y += 0.5;
              }
              
              // 调整种植的玫瑰大小（比跟随鼠标的更大，使其更明显）
              // 跟随鼠标的玫瑰是 0.5，种植的玫瑰设置为 1.5 使其更明显
              plantedRose.scale.set(6, 6, 6);
              plantedRose.position.copy(plantPosition);
              
              // 确保玫瑰可见
              plantedRose.visible = true;
              
              // 让玫瑰朝向法线方向（如果存在），否则朝向相机
              if (intersectNormal) {
                // 计算旋转，使玫瑰朝向法线方向
                const up = new THREE.Vector3(0, 1, 0);
                const quaternion = new THREE.Quaternion();
                quaternion.setFromUnitVectors(up, intersectNormal.clone().normalize());
                plantedRose.setRotationFromQuaternion(quaternion);
              } else {
                // 如果没有法线，让玫瑰朝向相机
                plantedRose.lookAt(cameraRef.current.position);
              }
              
              // 移除跟随鼠标的玫瑰
              if (cursorRoseRef.current && sceneRef.current) {
                sceneRef.current.remove(cursorRoseRef.current);
                cursorRoseRef.current.traverse((child) => {
                  if (child.geometry) child.geometry.dispose();
                  if (child.material) {
                    if (Array.isArray(child.material)) {
                      child.material.forEach(mat => {
                        if (mat.map) mat.map.dispose();
                        mat.dispose();
                      });
                    } else {
                      if (child.material.map) child.material.map.dispose();
                      child.material.dispose();
                    }
                  }
                });
                cursorRoseRef.current = null;
              }
              
              // 将玫瑰添加到场景
              if (sceneRef.current) {
                // 确保玫瑰在添加到场景前是可见的
                plantedRose.visible = true;
                plantedRose.traverse((child) => {
                  if (child.isMesh || child.isGroup) {
                    child.visible = true;
                  }
                });
                
                sceneRef.current.add(plantedRose);
                
                // 立即验证并打印详细信息
                const isInScene = sceneRef.current.children.includes(plantedRose);
                console.log('=== Rose Planting Debug ===');
                console.log('Rose added to scene at position:', plantPosition);
                console.log('Scene children count:', sceneRef.current.children.length);
                console.log('Planted rose visible:', plantedRose.visible);
                console.log('Planted rose position:', plantedRose.position);
                console.log('Planted rose scale:', plantedRose.scale);
                console.log('Planted rose is in scene:', isInScene);
                console.log('Planted rose world position:', plantedRose.getWorldPosition(new THREE.Vector3()));
                
                // 检查玫瑰的所有子对象
                let visibleChildren = 0;
                let totalChildren = 0;
                plantedRose.traverse((child) => {
                  totalChildren++;
                  if (child.visible) visibleChildren++;
                });
                console.log('Planted rose children - visible:', visibleChildren, 'total:', totalChildren);
                console.log('=== End Debug ===');
              } else {
                console.error('Scene ref is null, cannot add rose');
              }
              
              // 标记玫瑰已种植
              plantedRose.userData.isPlanted = true;
              plantedRose.userData.plantedOnPrince = true;
              plantedRose.userData.plantPosition = plantPosition.clone(); // 保存种植位置
              
              // 将种植的玫瑰添加到数组中，防止被清理
              plantedRosesRef.current.push(plantedRose);
              console.log('Planted roses count:', plantedRosesRef.current.length);
              
              // 取消携带状态
              setIsCarryingRose(false);
              isCarryingRoseRef.current = false;
              containerRef.current.style.cursor = 'default';
              
              // 更新物品栏（减少玫瑰数量或移除）
              setInventoryItems(prevItems => 
                prevItems.map(item => 
                  item.id === 1 && item.name === '玫瑰' 
                    ? { ...item, count: Math.max(0, item.count - 1) }
                    : item
                ).filter(item => item.count > 0 || item.id !== 1)
              );
              
              console.log('Rose planted on prince at position:', plantPosition);
              
              // 立即停止拖动，防止小王子跟随鼠标旋转
              isDraggingRef.current = false;
              containerRef.current.style.cursor = 'grab';
              
              return; // 不执行后续的视角恢复逻辑
            }
            
            // 如果没有携带玫瑰，检查是否是可点击的mesh（用于打开游戏）
            if (clickedMesh.userData.clickable) {
              console.log('Clicked on clickable mesh:', clickedMesh.name || 'unnamed');
              
              // 直接打开游戏弹框
              setShowUnityModal(true);
              console.log('Opening game modal');
            }
          }
        }
        
        // 如果当前显示的是月球+玫瑰，检测点击玫瑰
        if (currentModelValue === 'moon-rose' && roseRef.current && !roseClickedRef.current) {
          const intersects = raycasterRef.current.intersectObject(roseRef.current, true);
          
          if (intersects.length > 0) {
            const clickedMesh = intersects[0].object;
            
            if (clickedMesh.userData.clickable) {
              console.log('Clicked on rose:', clickedMesh.name || 'unnamed');
              
              // 设置玫瑰已点击状态
              setRoseClicked(true);
              roseClickedRef.current = true;
              
              // 计算月球+玫瑰的中心位置（用于相机lookAt）
              const moonCenter = new THREE.Vector3(0, 100, 0);
              
              // 设置相机目标位置：向上移动，俯视角度
              // 重置水平角度为0，确保倾斜方向固定
              targetSphericalRef.current.theta = 0;
              // phi角度越小，相机越靠上（俯视）
              // 设置一个较小的phi值，比如0.3（约17度俯视）
              targetSphericalRef.current.phi = 0.3;
              // 先重置相机距离到初始值，然后再拉近视角
              // 注意：不直接设置cameraSphericalRef.current.radius，让它通过插值平滑过渡
              const initialRadius = 500;
              targetSphericalRef.current.radius = initialRadius;
              
              targetSphericalRef.current.radius = Math.max(initialRadius - 200, 150);
                            
              // 记录点击时的相机状态，用于检测用户是否改变了视角
              roseClickedCameraStateRef.current = {
                radius: targetSphericalRef.current.radius,
                theta: targetSphericalRef.current.theta,
                phi: targetSphericalRef.current.phi
              };
              
              // 停止月球和玫瑰的旋转，先将月球转回初始位置
              if (moonRef.current) {
                // 设置目标y轴旋转为0（初始位置）
                moonRef.current.userData.targetRotationY = 0;
                // 标记需要先回到初始位置
                moonRef.current.userData.needsResetRotation = true;
                
                // 设置目标倾斜角度（基于世界坐标系，不依赖当前旋转）
                // 绕x轴向后倾斜（负值），让玫瑰朝左上方
                const tiltAngleX = Math.PI / 6; // 30度，向后倾斜（向上）
                // 绕z轴向右旋转，让玫瑰朝右（修正左右方向）
                const tiltAngleZ = Math.PI / 6; // 30度，向右旋转
                
                moonRef.current.userData.targetRotationX = tiltAngleX;
                moonRef.current.userData.targetRotationZ = tiltAngleZ;
              }
              
              // 玫瑰是月球的子对象，不需要单独设置倾斜，会跟随月球
              
              console.log('Rose clicked, camera moving to top view');
            }
          }
        }
      }
      
      isDraggingRef.current = false;
      containerRef.current.style.cursor = 'grab';
      event.preventDefault(); // 防止默认行为
    };

    // 鼠标滚轮处理（控制相机距离）
    const handleWheel = (event) => {
      event.preventDefault();
      
      // 滚轮向上（deltaY < 0）时拉近，向下（deltaY > 0）时拉远
      const zoomSpeed = 20; // 每次滚动的距离变化量
      const minDistance = 100; // 最小距离（不能太近）
      const maxDistance = 1500; // 最大距离（不能太远）
      
      // 更新目标距离（使用球坐标系的radius）
      targetSphericalRef.current.radius += event.deltaY > 0 ? zoomSpeed : -zoomSpeed;
      
      // 限制在最小和最大距离之间
      targetSphericalRef.current.radius = Math.max(minDistance, Math.min(maxDistance, targetSphericalRef.current.radius));
      
      // 如果正在携带玫瑰，立即更新玫瑰位置以跟随相机缩放
      if (isCarryingRoseRef.current && cursorRoseRef.current && updateCursorRosePositionRef.current) {
        // 使用最新的鼠标位置更新
        const currentMouseX = mousePosition.x || window.innerWidth / 2;
        const currentMouseY = mousePosition.y || window.innerHeight / 2;
        updateCursorRosePositionRef.current(currentMouseX, currentMouseY);
      }
    };

    // 窗口大小调整
    const handleResize = () => {
      windowHalfXRef.current = window.innerWidth / 2;
      windowHalfYRef.current = window.innerHeight / 2;

      camera.aspect = window.innerWidth / window.innerHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(window.innerWidth, window.innerHeight);
    };

    // 渲染函数
    const render = () => {
      if (!cameraRef.current || !sceneRef.current || !rendererRef.current) return;

      const camera = cameraRef.current;
      const scene = sceneRef.current;
      const renderer = rendererRef.current;

      // 使用球坐标系控制相机，实现360度无死角旋转
      const princeCenter = new THREE.Vector3(0, 0, 0); // 小王子在场景中心
      const moonCenter = new THREE.Vector3(0, 100, 0); // 月球在y:100
      
      // 根据当前模型选择中心点
      const modelValue = currentModelRef.current;
      const centerPoint = modelValue === 'moon-rose' ? moonCenter : princeCenter;
      
      // 如果正在恢复视角到初始值（点击小王子后），检查是否已经到达初始值
      if (isRestoringViewRef.current && modelValue === 'prince') {
        const initialView = princeInitialViewRef.current;
        const currentRadius = cameraSphericalRef.current.radius;
        const currentTheta = cameraSphericalRef.current.theta;
        const currentPhi = cameraSphericalRef.current.phi;
        
        // 计算与初始值的差值
        const radiusDiff = Math.abs(currentRadius - initialView.radius);
        const thetaDiff = Math.abs(currentTheta - initialView.theta);
        const phiDiff = Math.abs(currentPhi - initialView.phi);
        
        // 阈值：判断是否已经到达初始值
        const threshold = {
          radius: 5, // 距离变化阈值
          theta: 0.02, // 水平角度变化阈值（约1度）
          phi: 0.02 // 垂直角度变化阈值（约1度）
        };
        
        // 如果已经到达初始值，切换模型
        if (radiusDiff < threshold.radius && thetaDiff < threshold.theta && phiDiff < threshold.phi) {
          console.log('View restored to initial position, switching to moon-rose');
          
          // 检查模型是否需要重新加载
          const moonValid = moonRef.current && moonLoadedRef.current && scene.children.includes(moonRef.current);
          const roseValid = roseRef.current && roseLoadedRef.current && 
                           (moonRef.current?.children.includes(roseRef.current) || scene.children.includes(roseRef.current));
          
          if (!moonValid || !roseValid) {
            console.log('Models missing, reloading before switching...');
            // 如果加载函数存在，调用它重新加载
            if (loadMoonRoseRef.current) {
              loadMoonRoseRef.current();
            }
            // 等待一帧后继续切换，确保加载函数被调用
            requestAnimationFrame(() => {
              setCurrentModel('moon-rose');
              currentModelRef.current = 'moon-rose';
            });
          } else {
            console.log('Models already exist, switching without reload');
            // 模型已存在，直接切换
            setCurrentModel('moon-rose');
            currentModelRef.current = 'moon-rose';
          }
          
          // 重置玫瑰点击状态
          setRoseClicked(false);
          roseClickedRef.current = false;
          
          // 重置相机距离和角度到月球+玫瑰的初始值
          const moonInitialRadius = 500;
          const moonInitialTheta = 0; // 水平角度重置为0
          const moonInitialPhi = Math.PI / 2; // 垂直角度重置为水平视角
          
          targetSphericalRef.current.radius = moonInitialRadius;
          targetSphericalRef.current.theta = moonInitialTheta;
          targetSphericalRef.current.phi = moonInitialPhi;
          
          cameraSphericalRef.current.radius = moonInitialRadius;
          cameraSphericalRef.current.theta = moonInitialTheta;
          cameraSphericalRef.current.phi = moonInitialPhi;
          
          // 立即更新可见性，确保切换立即生效（只有在模型加载完成后才设置）
          if (princeRef.current && princeLoadedRef.current) {
            princeRef.current.visible = false;
          }
          if (moonRef.current && moonLoadedRef.current) {
            moonRef.current.visible = true;
            console.log('Moon visible set to true');
          }
          if (roseRef.current && roseLoadedRef.current) {
            roseRef.current.visible = true;
            console.log('Rose visible set to true');
          }
          
          // 隐藏所有种植的玫瑰
          if (plantedRosesRef.current && plantedRosesRef.current.length > 0) {
            plantedRosesRef.current.forEach((rose) => {
              if (rose) {
                rose.visible = false;
                rose.traverse((child) => {
                  if (child.isMesh || child.isGroup) {
                    child.visible = false;
                  }
                });
              }
            });
            console.log('Hiding all planted roses when switching to moon-rose');
          }
          
          // 清除恢复视角标记
          isRestoringViewRef.current = false;
        }
      }
      
      // 如果按钮显示时（roseClicked为true），检测用户是否改变了视角
      if (roseClickedRef.current) {
        const savedState = roseClickedCameraStateRef.current;
        const currentState = {
          radius: targetSphericalRef.current.radius,
          theta: targetSphericalRef.current.theta,
          phi: targetSphericalRef.current.phi
        };
        
        // 检测是否有显著变化（允许小的误差）
        const radiusDiff = Math.abs(currentState.radius - savedState.radius);
        const thetaDiff = Math.abs(currentState.theta - savedState.theta);
        const phiDiff = Math.abs(currentState.phi - savedState.phi);
        
        // 如果变化超过阈值，隐藏按钮并恢复旋转
        const threshold = {
          radius: 10, // 距离变化阈值
          theta: 0.05, // 水平角度变化阈值（约3度）
          phi: 0.05 // 垂直角度变化阈值（约3度）
        };
        
        if (radiusDiff > threshold.radius || thetaDiff > threshold.theta || phiDiff > threshold.phi) {
          // 用户改变了视角，隐藏按钮并恢复旋转
          setRoseClicked(false);
          roseClickedRef.current = false;
          console.log('Camera changed, hiding button and restoring rotation');
        }
      }
      
      // 平滑更新球坐标（用于滚轮控制的距离）
      // 使用更慢的插值速度，让动画更平滑
      const lerpSpeed = 0.03; // 从0.1降低到0.03，让动画更慢更平滑
      
      if (isDraggingRef.current) {
        // 拖动时：角度立即更新，距离平滑更新
        cameraSphericalRef.current.theta = targetSphericalRef.current.theta;
        cameraSphericalRef.current.phi = targetSphericalRef.current.phi;
        cameraSphericalRef.current.radius += (targetSphericalRef.current.radius - cameraSphericalRef.current.radius) * lerpSpeed;
      } else {
        // 非拖动时：所有参数都平滑更新
        cameraSphericalRef.current.theta += (targetSphericalRef.current.theta - cameraSphericalRef.current.theta) * lerpSpeed;
        cameraSphericalRef.current.phi += (targetSphericalRef.current.phi - cameraSphericalRef.current.phi) * lerpSpeed;
        cameraSphericalRef.current.radius += (targetSphericalRef.current.radius - cameraSphericalRef.current.radius) * lerpSpeed;
      }
      
      // 根据当前模型决定是否固定垂直角度
      if (modelValue === 'prince') {
        // 显示小王子时，强制固定垂直角度，只允许水平旋转
        cameraSphericalRef.current.phi = Math.PI / 2;
        targetSphericalRef.current.phi = Math.PI / 2;
      }
      // 显示月球+玫瑰时，允许垂直旋转，不进行限制
      
      // 将球坐标转换为笛卡尔坐标
      const spherical = cameraSphericalRef.current;
      camera.position.set(
        centerPoint.x + spherical.radius * Math.sin(spherical.phi) * Math.cos(spherical.theta),
        centerPoint.y + spherical.radius * Math.cos(spherical.phi),
        centerPoint.z + spherical.radius * Math.sin(spherical.phi) * Math.sin(spherical.theta)
      );
      
      // 相机始终朝向当前模型的中心
      camera.lookAt(centerPoint);
      
      // 如果正在携带玫瑰，确保玫瑰始终可见且在最前面
      // 注意：位置更新已经在 handleMouseMove 中直接处理，这里只确保可见性
      if (isCarryingRoseRef.current && cursorRoseRef.current) {
        cursorRoseRef.current.visible = true;
        cursorRoseRef.current.renderOrder = 999; // 设置高渲染顺序，确保在最前面
      }
      
      // 根据当前模型状态控制种植的玫瑰的可见性
      // 只在显示小王子时显示种植的玫瑰
      const shouldShowPlantedRoses = modelValue === 'prince';
      if (plantedRosesRef.current && plantedRosesRef.current.length > 0) {
        plantedRosesRef.current.forEach((rose) => {
          if (rose && sceneRef.current && sceneRef.current.children.includes(rose)) {
            rose.visible = shouldShowPlantedRoses;
            // 确保种植的玫瑰也在最前面渲染（仅在可见时）
            if (shouldShowPlantedRoses) {
              rose.traverse((child) => {
                if (child.isMesh || child.isGroup) {
                  child.visible = true;
                  child.renderOrder = 998; // 比跟随鼠标的玫瑰稍低，但比普通对象高
                }
              });
            } else {
              // 隐藏时也隐藏所有子对象
              rose.traverse((child) => {
                if (child.isMesh || child.isGroup) {
                  child.visible = false;
                }
              });
            }
          } else if (rose && !sceneRef.current?.children.includes(rose) && shouldShowPlantedRoses) {
            // 如果玫瑰不在场景中且应该显示，重新添加
            console.warn('Planted rose not in scene, re-adding:', rose);
            if (sceneRef.current) {
              sceneRef.current.add(rose);
            }
          }
        });
      }
      
      // 也检查场景中所有标记为种植的对象
      if (sceneRef.current) {
        sceneRef.current.traverse((object) => {
          if (object.userData && object.userData.isPlanted) {
            object.visible = shouldShowPlantedRoses;
            // 确保种植的玫瑰也在最前面渲染（仅在可见时）
            if (shouldShowPlantedRoses && (object.isMesh || object.isGroup)) {
              object.renderOrder = 998;
            }
          }
        });
      }

      // 只旋转粒子系统（星空背景），不旋转整个场景，避免模型跟着旋转
      if (particlesRef.current) {
        particlesRef.current.rotation.x += 0.001;
        particlesRef.current.rotation.y += 0.002;
      }

      // 根据currentModel切换显示/隐藏模型
      // 每次渲染都强制更新可见性，确保状态正确
      
      // 如果当前模型是moon-rose但模型不存在，强制重新加载
      if (modelValue === 'moon-rose' && (!moonRef.current || !moonLoadedRef.current || !roseRef.current || !roseLoadedRef.current)) {
        // 使用节流，避免每帧都触发重新加载
        // 使用一个全局标记来跟踪是否正在重新加载
        if (!sceneRef.current?.userData?.reloadingMoonRose) {
          console.warn('Moon or Rose model not loaded in render loop, forcing reload...');
          if (sceneRef.current) {
            sceneRef.current.userData.reloadingMoonRose = true;
          }
          if (loadMoonRoseRef.current) {
            loadMoonRoseRef.current();
          }
        }
      }
      
      // 显示/隐藏小王子（只有在模型加载完成后才显示）
      if (princeRef.current && princeLoadedRef.current) {
        const shouldShowPrince = modelValue === 'prince';
        princeRef.current.visible = shouldShowPrince;
      }
      
      // 调试：检查种植的玫瑰是否还在场景中
      if (plantedRosesRef.current && plantedRosesRef.current.length > 0) {
        plantedRosesRef.current.forEach((rose, index) => {
          if (rose) {
            const isInScene = sceneRef.current && sceneRef.current.children.includes(rose);
            const worldPos = rose.getWorldPosition(new THREE.Vector3());
            const distanceToCamera = camera.position.distanceTo(worldPos);
            
            // 每60帧打印一次调试信息（避免刷屏）
            if (!rose.debugFrameCount) rose.debugFrameCount = 0;
            rose.debugFrameCount++;
            if (rose.debugFrameCount % 60 === 0) {
              // console.log(`Planted rose ${index}:`, {
              //   inScene: isInScene,
              //   visible: rose.visible,
              //   worldPos: worldPos,
              //   distanceToCamera: distanceToCamera,
              //   scale: rose.scale
              // });
            }
            
            // 如果玫瑰不在场景中且应该显示，重新添加
            if (!isInScene && sceneRef.current && modelValue === 'prince') {
              console.warn('Planted rose not in scene, re-adding:', index);
              sceneRef.current.add(rose);
            }
            
            // 根据当前模型状态设置可见性
            const shouldShow = modelValue === 'prince';
            rose.visible = shouldShow;
            rose.traverse((child) => {
              if (child.isMesh || child.isGroup) {
                child.visible = shouldShow;
              }
            });
          }
        });
      }
      
      // 显示/隐藏月球和玫瑰（只有在模型加载完成后才显示）
      // 注意：即使模型还没加载完成，渲染循环也会持续检查，一旦加载完成就会更新
      if (moonRef.current && moonLoadedRef.current) {
        const shouldShowMoon = modelValue === 'moon-rose';
        // 强制设置可见性，确保每次渲染都更新（不使用条件判断，直接设置）
        moonRef.current.visible = shouldShowMoon;
        
        // 月球自转和浮动（只有在玫瑰未点击时才旋转）
        if (shouldShowMoon && !roseClickedRef.current) {
        moonRef.current.rotation.y += 0.005;
        // 也可以添加轻微的上下浮动效果
        moonRef.current.position.y = 100 + Math.sin(Date.now() * 0.001) * 10;
        }
        
        // 如果玫瑰已点击（俯视状态），应用倾斜（绕x轴和z轴）
        // 玫瑰会跟随月球倾斜，因为它是月球的子对象
        if (shouldShowMoon && roseClickedRef.current) {
          // 使用与相机移动一致的插值速度（0.03）
          const rotationLerpSpeed = 0.03;
          
          // 先将y轴旋转回到初始位置（0）
          if (moonRef.current.userData.targetRotationY !== undefined) {
            const targetY = moonRef.current.userData.targetRotationY;
            const currentY = moonRef.current.rotation.y;
            const deltaY = targetY - currentY;
            
            // 处理角度归一化（确保选择最短路径）
            let normalizedDeltaY = deltaY;
            if (normalizedDeltaY > Math.PI) {
              normalizedDeltaY -= 2 * Math.PI;
            } else if (normalizedDeltaY < -Math.PI) {
              normalizedDeltaY += 2 * Math.PI;
            }
            
            // 使用与相机一致的插值速度，让旋转更丝滑
            moonRef.current.rotation.y += normalizedDeltaY * rotationLerpSpeed;
            
            // 如果y轴旋转已经接近目标（误差小于0.02），同时开始应用倾斜
            // 这样可以实现更自然的衔接
            const yRotationThreshold = 0.02;
            const yRotationProgress = 1 - Math.min(Math.abs(normalizedDeltaY) / Math.PI, 1);
            
            // 根据y轴旋转进度，同时应用x和z轴的倾斜，实现平滑衔接
            if (moonRef.current.userData.targetRotationX !== undefined) {
              const targetX = moonRef.current.userData.targetRotationX;
              // 使用与相机一致的插值速度
              moonRef.current.rotation.x += (targetX - moonRef.current.rotation.x) * rotationLerpSpeed;
            }
            
            if (moonRef.current.userData.targetRotationZ !== undefined) {
              const targetZ = moonRef.current.userData.targetRotationZ;
              // 使用与相机一致的插值速度
              moonRef.current.rotation.z += (targetZ - moonRef.current.rotation.z) * rotationLerpSpeed;
            }
            
            // 如果y轴旋转完成，标记复位完成
            if (Math.abs(normalizedDeltaY) < yRotationThreshold) {
              moonRef.current.rotation.y = targetY; // 精确设置为目标值
              moonRef.current.userData.needsResetRotation = false;
            }
          }
        } else {
          // 如果不在俯视状态，恢复垂直（平滑过渡回0）
          const rotationLerpSpeed = 0.03; // 使用与相机一致的插值速度
          moonRef.current.rotation.x += (0 - moonRef.current.rotation.x) * rotationLerpSpeed;
          moonRef.current.rotation.z += (0 - moonRef.current.rotation.z) * rotationLerpSpeed;
          // 清除复位标记
          if (moonRef.current.userData) {
            moonRef.current.userData.needsResetRotation = false;
          }
        }
      }
      
      // 玫瑰跟随月球显示/隐藏（因为玫瑰是月球的子对象）
      // 注意：即使玫瑰是月球的子对象，也需要单独设置visible，因为Three.js中
      // 如果子对象的visible为false，即使父对象可见，子对象也不会显示
      // 注意：即使模型还没加载完成，渲染循环也会持续检查，一旦加载完成就会更新
      if (roseRef.current && roseLoadedRef.current) {
        const shouldShowRose = modelValue === 'moon-rose';
        // 强制设置可见性，确保每次渲染都更新（不使用条件判断，直接设置）
        roseRef.current.visible = shouldShowRose;
        
        // 玫瑰旋转（只有在玫瑰未点击时才旋转）
        // 注意：玫瑰是月球的子对象，所以会跟随月球旋转和倾斜
        if (shouldShowRose && !roseClickedRef.current) {
          roseRef.current.rotation.y += 0.002;
        }
        
        // 玫瑰不需要单独设置倾斜，因为它是月球的子对象，会跟随月球倾斜
      }

      renderer.render(scene, camera);
    };

    // 动画循环
    const animate = () => {
      animationFrameRef.current = requestAnimationFrame(animate);
      render();
    };

    animate();

    // 添加事件监听
    containerRef.current.style.touchAction = 'none';
    containerRef.current.style.cursor = 'grab'; // 设置鼠标样式
    containerRef.current.style.userSelect = 'none'; // 防止拖动时选中文本
    
    // 使用capture模式确保事件能正确捕获
    containerRef.current.addEventListener('pointerdown', handlePointerDown, { passive: false });
    containerRef.current.addEventListener('pointermove', handlePointerMove, { passive: false });
    containerRef.current.addEventListener('pointerup', handlePointerUp, { passive: false });
    containerRef.current.addEventListener('pointercancel', handlePointerUp, { passive: false }); // 指针取消时也结束拖动
    containerRef.current.addEventListener('pointerleave', handlePointerUp, { passive: false }); // 鼠标离开时也结束拖动
    containerRef.current.addEventListener('wheel', handleWheel, { passive: false });
    // 添加鼠标移动事件，用于更新跟随鼠标的玫瑰位置
    // 在窗口级别监听，确保即使鼠标移出容器也能更新
    window.addEventListener('mousemove', handleMouseMove, { passive: true });
    window.addEventListener('resize', handleResize);

    // 清理函数
    return () => {
      if (containerRef.current) {
        containerRef.current.removeEventListener('pointerdown', handlePointerDown);
        containerRef.current.removeEventListener('pointermove', handlePointerMove);
        containerRef.current.removeEventListener('pointerup', handlePointerUp);
        containerRef.current.removeEventListener('pointercancel', handlePointerUp);
        containerRef.current.removeEventListener('pointerleave', handlePointerUp);
        containerRef.current.removeEventListener('wheel', handleWheel);
      }
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('resize', handleResize);
      
      // 清理跟随鼠标的玫瑰模型
      if (cursorRoseRef.current && sceneRef.current) {
        sceneRef.current.remove(cursorRoseRef.current);
        cursorRoseRef.current.traverse((child) => {
          if (child.geometry) child.geometry.dispose();
          if (child.material) {
            if (Array.isArray(child.material)) {
              child.material.forEach(mat => {
                if (mat.map) mat.map.dispose();
                mat.dispose();
              });
            } else {
              if (child.material.map) child.material.map.dispose();
              child.material.dispose();
            }
          }
        });
        cursorRoseRef.current = null;
      }
      
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      
      if (containerRef.current && rendererRef.current && rendererRef.current.domElement) {
        containerRef.current.removeChild(rendererRef.current.domElement);
      }
      
      if (rendererRef.current) {
        rendererRef.current.dispose();
      }
      
      if (particlesRef.current) {
        particlesRef.current.geometry.dispose();
        particlesRef.current.material.dispose();
      }

      // 清理小王子模型资源
      if (princeRef.current) {
        princeRef.current.traverse((child) => {
          if (child.isMesh) {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat.map) mat.map.dispose();
                  mat.dispose();
                });
              } else {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
              }
            }
          }
        });
        scene.remove(princeRef.current);
      }
      
      // 清理月球和玫瑰模型资源（包括玫瑰，因为它是月球的子对象）
      if (moonRef.current) {
        moonRef.current.traverse((child) => {
          if (child.isMesh) {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat.map) mat.map.dispose();
                  mat.dispose();
                });
              } else {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
              }
            }
          }
        });
        scene.remove(moonRef.current);
      }
      
      // 清理引用和加载状态
      princeRef.current = null;
      moonRef.current = null;
      roseRef.current = null;
      princeLoadedRef.current = false;
      moonLoadedRef.current = false;
      roseLoadedRef.current = false;
    };
  }, []);


  // 打开Unity弹框
  const handleOpenUnityModal = () => {
    setShowUnityModal(true);
  };

  // 关闭Unity弹框
  const handleCloseUnityModal = () => {
    setShowUnityModal(false);
  };

  // 切换到小王子模型的函数
  const handleSwitchToPrince = () => {
    setCurrentModel('prince');
    currentModelRef.current = 'prince';
    // 重置玫瑰点击状态
    setRoseClicked(false);
    roseClickedRef.current = false;
    // 清除恢复视角标记（如果存在）
    isRestoringViewRef.current = false;
    
    // 重置相机距离和角度到初始值（使用princeInitialViewRef的值）
    const initialView = princeInitialViewRef.current;
    
    targetSphericalRef.current.radius = initialView.radius;
    targetSphericalRef.current.theta = initialView.theta;
    targetSphericalRef.current.phi = initialView.phi;
    
    cameraSphericalRef.current.radius = initialView.radius;
    cameraSphericalRef.current.theta = initialView.theta;
    cameraSphericalRef.current.phi = initialView.phi;
    
    // 立即更新可见性（只有在模型加载完成后才设置）
    if (princeRef.current && princeLoadedRef.current) {
      princeRef.current.visible = true;
    }
    if (moonRef.current && moonLoadedRef.current) {
      moonRef.current.visible = false;
    }
    if (roseRef.current && roseLoadedRef.current) {
      roseRef.current.visible = false;
    }
    
    // 显示所有种植的玫瑰
    if (plantedRosesRef.current && plantedRosesRef.current.length > 0) {
      plantedRosesRef.current.forEach((rose) => {
        if (rose && sceneRef.current) {
          // 确保玫瑰在场景中
          if (!sceneRef.current.children.includes(rose)) {
            sceneRef.current.add(rose);
          }
          // 设置为可见
          rose.visible = true;
          rose.traverse((child) => {
            if (child.isMesh || child.isGroup) {
              child.visible = true;
            }
          });
        }
      });
      console.log('Showing all planted roses when switching to prince');
    }
  };

  // 处理物品点击
  const handleItemClick = (item) => {
    console.log('Item clicked:', item);
    
    // 如果点击的是玫瑰，且当前显示的是小王子模型
    if (item.id === 1 && item.name === '玫瑰' && currentModel === 'prince') {
      if (isCarryingRose) {
        // 如果已经在携带，取消携带
        setIsCarryingRose(false);
        isCarryingRoseRef.current = false;
        // 移除跟随鼠标的玫瑰模型
        if (cursorRoseRef.current && sceneRef.current) {
          sceneRef.current.remove(cursorRoseRef.current);
          // 清理资源
          cursorRoseRef.current.traverse((child) => {
            if (child.geometry) child.geometry.dispose();
            if (child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach(mat => {
                  if (mat.map) mat.map.dispose();
                  mat.dispose();
                });
              } else {
                if (child.material.map) child.material.map.dispose();
                child.material.dispose();
              }
            }
          });
          cursorRoseRef.current = null;
        }
        containerRef.current.style.cursor = 'default';
      } else {
        // 开始携带玫瑰，创建跟随鼠标的玫瑰模型
        setIsCarryingRose(true);
        isCarryingRoseRef.current = true;
        createCursorRose();
        containerRef.current.style.cursor = 'none'; // 隐藏默认鼠标
      }
    }
  };
  
  // 创建跟随鼠标的玫瑰模型
  const createCursorRose = () => {
    if (!sceneRef.current || !cameraRef.current || cursorRoseRef.current) return;
    
    const roseLoader = new GLTFLoader();
    const roseModelDir = roseModelPath.substring(0, roseModelPath.lastIndexOf('/') + 1);
    roseLoader.setPath(roseModelDir);
    const roseFileName = roseModelPath.substring(roseModelPath.lastIndexOf('/') + 1);
    
    // 加载纹理
    const textureLoader = new THREE.TextureLoader();
    const textureBasePath = roseModelDir + 'textures/';
    const diffuseTexture = textureLoader.load(
      textureBasePath + 'Red_rose_diffuse.jpeg',
      (texture) => {
        texture.flipY = false;
        texture.needsUpdate = true;
      }
    );
    
    roseLoader.load(
      roseFileName,
      (gltf) => {
        const rose = gltf.scene.clone(); // 克隆模型，避免影响原始模型
        
        // 调整玫瑰大小（适合跟随鼠标的大小）
        const scaleFactor = 0.5; // 增加缩放，让玫瑰更明显（从0.15增加到0.5）
        rose.scale.set(scaleFactor, scaleFactor, scaleFactor);
        
        // 确保玫瑰可见
        rose.visible = true;
        
        // 调整旋转
        rose.rotation.y = Math.PI / 4;
        rose.rotation.x = 0;
        rose.rotation.z = 0;
        
        // 应用纹理
        rose.traverse((child) => {
          if (child.isMesh) {
            // 设置高渲染顺序，确保玫瑰在最前面显示
            child.renderOrder = 999;
            
            if (child.material) {
              if (Array.isArray(child.material)) {
                child.material.forEach((mat) => {
                  if (mat) {
                    mat.map = diffuseTexture;
                    mat.map.needsUpdate = true;
                    mat.needsUpdate = true;
                    mat.fog = false;
                    mat.depthTest = true; // 启用深度测试
                    mat.depthWrite = true; // 启用深度写入
                    if (mat.emissive) {
                      mat.emissive.setHex(0x111111);
                    }
                    mat.emissiveIntensity = 0.15;
                  }
                });
              } else {
                child.material.map = diffuseTexture;
                child.material.map.needsUpdate = true;
                child.material.needsUpdate = true;
                child.material.fog = false;
                child.material.depthTest = true; // 启用深度测试
                child.material.depthWrite = true; // 启用深度写入
                if (child.material.emissive) {
                  child.material.emissive.setHex(0x111111);
                }
                child.material.emissiveIntensity = 0.15;
              }
            }
          }
        });
        
        // 标记为跟随鼠标的玫瑰
        rose.userData.isCursorRose = true;
        
        sceneRef.current.add(rose);
        cursorRoseRef.current = rose;
        
        console.log('Cursor rose created, position:', rose.position, 'visible:', rose.visible);
        console.log('Scene:', sceneRef.current, 'Camera:', cameraRef.current);
        
        // 立即更新到当前鼠标位置（使用最新的鼠标位置）
        // 使用 setTimeout 确保 updateCursorRosePositionRef 已经设置
        setTimeout(() => {
          if (updateCursorRosePositionRef.current) {
            const currentMouseX = mousePosition.x || window.innerWidth / 2;
            const currentMouseY = mousePosition.y || window.innerHeight / 2;
            console.log('Updating cursor rose position to:', currentMouseX, currentMouseY);
            updateCursorRosePositionRef.current(currentMouseX, currentMouseY);
            console.log('Cursor rose updated position:', cursorRoseRef.current?.position);
          } else {
            console.warn('updateCursorRosePositionRef not set yet');
          }
        }, 100);
      },
      undefined,
      (error) => {
        console.error('Error loading cursor rose:', error);
      }
    );
  };
  
  // 更新跟随鼠标的玫瑰位置的ref（在useEffect中设置）
  const updateCursorRosePositionRef = useRef(null);

  return (
    <div className="starportal-planb-root" ref={containerRef}>
      {currentModel === 'moon-rose' && roseClicked && !showUnityModal && (
        <button 
          className="start-rose-journey-button"
          onClick={handleSwitchToPrince}
        >
          返回心海
        </button>
      )}
      
      {currentModel === 'prince' && (
        <>
          <Inventory
            items={inventoryItems}
            onItemClick={handleItemClick}
            visible={showInventory}
            collapsed={inventoryCollapsed}
            onCollapseToggle={(collapsed) => setInventoryCollapsed(collapsed)}
          />
        </>
      )}
      
      <Modal 
        open={showUnityModal} 
        onClose={handleCloseUnityModal}
        isFullscreen={true}
        afterClose={() => {
          // 关闭模态框时重置视频状态
          setIsVideoLoaded(false);
          setShowEndVideo(false);
        }}
      >
        {/* 结束转场视频 */}
        {showEndVideo && (
          <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
            <video
              ref={endVideoRef}
              src="/end.mp4"
              autoPlay
              muted
              playsInline
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                position: 'absolute',
                top: 0,
                left: 0
              }}
              onEnded={() => {
                // 视频播放完成后关闭弹框
                console.log('End video finished, closing modal');
                setShowUnityModal(false);
                setShowEndVideo(false);
              }}
              onError={(e) => {
                console.error('Error playing end video:', e);
                // 如果视频播放出错，直接关闭弹框
                setShowUnityModal(false);
                setShowEndVideo(false);
              }}
            />
          </div>
        )}
        
        {/* 视频加载页面 */}
        {!isVideoLoaded && !showEndVideo && (
          <div style={{ width: '100%', height: '100%', position: 'relative', overflow: 'hidden' }}>
            <video
              ref={videoRef}
              src="/loading.mp4"
              autoPlay
              loop
              muted
              playsInline
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                position: 'absolute',
                top: 0,
                left: 0
              }}
              onLoadedData={() => {
                // 视频加载完成后，设置定时器显示Unity游戏
                // 这里可以根据需要调整显示时间，或者在视频播放结束后显示
                setTimeout(() => {
                  setIsVideoLoaded(true);
                }, 5000); // 5秒后显示Unity游戏
              }}
            />
          </div>
        )}
        
        {/* Unity游戏iframe */}
        <iframe
          ref={iframeRef}
          src={UNITY_IFRAME_URL}
          style={{
            width: '100%',
            height: '100%',
            border: 'none',
            display: isVideoLoaded && !showEndVideo ? 'block' : 'none'
          }}
          title="Unity WebGL"
          allow="fullscreen"
          onLoad={() => {
            // iframe加载完成
          }}
        />
      </Modal>
    </div>
  );
}

