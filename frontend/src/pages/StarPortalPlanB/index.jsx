import React, { useEffect, useRef } from "react";
import "./styles/index.css";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import moonModelPath from "./styles/img/the_old_moon/scene.gltf?url";

export default function StarPortalPlanB() {
  const containerRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const particlesRef = useRef(null);
  const materialRef = useRef(null);
  const moonRef = useRef(null);
  const animationFrameRef = useRef(null);
  
  const mouseXRef = useRef(0);
  const mouseYRef = useRef(0);
  const windowHalfXRef = useRef(window.innerWidth / 2);
  const windowHalfYRef = useRef(window.innerHeight / 2);

  useEffect(() => {
    if (!containerRef.current) return;

    // 创建相机
    const camera = new THREE.PerspectiveCamera(
      50,
      window.innerWidth / window.innerHeight,
      1,
      3000
    );
    camera.position.set(0, 0, 500);
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
                      mat.emissive.setHex(0x444444); // 添加轻微的自发光
                    }
                    mat.emissiveIntensity = 0.3; // 设置自发光强度
                  }
                });
              } else {
                child.material.fog = false; // 禁用雾效对月亮的影响
                // 增加材质的自发光，让月亮更亮
                if (child.material.emissive) {
                  child.material.emissive.setHex(0x444444); // 添加轻微的自发光
                }
                child.material.emissiveIntensity = 0.3; // 设置自发光强度
              }
            }
          }
        });
        scene.add(moon);
        moonRef.current = moon;
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
      }
    );

    // 添加环境光（增强亮度以更好地显示纹理）
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.5);
    scene.add(ambientLight);

    // 添加点光源（模拟太阳光照射月球）
    const pointLight = new THREE.PointLight(0xffffff, 2.5, 1000);
    pointLight.position.set(300, 200, 400);
    scene.add(pointLight);
    
    // 添加额外的定向光源，从正面照射月亮
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.5);
    directionalLight.position.set(0, 100, 500);
    scene.add(directionalLight);

    // 创建渲染器
    const renderer = new THREE.WebGLRenderer();
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(window.innerWidth, window.innerHeight);
    containerRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // 鼠标移动处理
    const handlePointerMove = (event) => {
      mouseXRef.current = event.clientX - windowHalfXRef.current;
      mouseYRef.current = event.clientY - windowHalfYRef.current;
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

      // 相机跟随鼠标移动（限制移动范围，确保月球在视野内）
      const maxOffset = 200; // 最大偏移量
      const targetX = Math.max(-maxOffset, Math.min(maxOffset, -mouseXRef.current * 2));
      const targetY = Math.max(-maxOffset, Math.min(maxOffset, mouseYRef.current * 2));
      camera.position.x += (targetX - camera.position.x) * 0.02;
      camera.position.y += (targetY - camera.position.y) * 0.02;
      // 相机始终朝向场景中心，确保月球在视野内
      camera.lookAt(0, 100, 0);

      // 场景旋转
      scene.rotation.x += 0.001;
      scene.rotation.y += 0.002;

      // 月球自转
      if (moonRef.current) {
        moonRef.current.rotation.y += 0.005;
        // 也可以添加轻微的上下浮动效果
        moonRef.current.position.y = 100 + Math.sin(Date.now() * 0.001) * 10;
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
    containerRef.current.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('resize', handleResize);

    // 清理函数
    return () => {
      if (containerRef.current) {
        containerRef.current.removeEventListener('pointermove', handlePointerMove);
      }
      window.removeEventListener('resize', handleResize);
      
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

      if (moonRef.current) {
        // 清理 GLTF 模型资源
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
    };
  }, []);


  return (
    <div className="starportal-planb-root" ref={containerRef}>
      {/* 可以在这里添加其他UI元素 */}
    </div>
  );
}

