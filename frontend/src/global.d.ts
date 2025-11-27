/**
 * Live2D Cubism Core 全局类型声明
 * 这个文件声明了由 live2dcubismcore.min.js 提供的全局变量
 */

declare namespace Live2DCubismCore {
  interface Model {
    parameters: {
      count: number;
      ids: string[];
      values: Float32Array;
      maximumValues: Float32Array;
      minimumValues: Float32Array;
      defaultValues: Float32Array;
    };
    parts: {
      count: number;
      ids: string[];
      opacities: Float32Array;
    };
    drawables: {
      count: number;
      ids: string[];
      constantFlags: Uint8Array;
      dynamicFlags: Uint8Array;
      textureIndices: Int32Array;
      drawOrders: Int32Array;
      renderOrders: Int32Array;
      opacities: Float32Array;
      maskCounts: Int32Array;
      masks: Int32Array[];
      indexCounts: Int32Array;
      vertexCounts: Int32Array;
      indices: Uint16Array[];
      vertexPositions: Float32Array[];
      vertexUvs: Float32Array[];
    };
    canvasinfo: {
      CanvasWidth: number;
      CanvasHeight: number;
      PixelsPerUnit: number;
    };
    release(): void;
    update(): void;
  }

  interface Moc {
    release(): void;
  }

  namespace Moc {
    function fromArrayBuffer(buffer: ArrayBuffer, size: number): Moc;
  }

  namespace Model {
    function fromMoc(moc: Moc): Model;
  }

  namespace Utils {
    function hasVertexPositionsDidChangeBit(flag: number): boolean;
    function hasIsDoubleSidedBit(flag: number): boolean;
    function hasBlendAdditiveBit(flag: number): boolean;
    function hasBlendMultiplicativeBit(flag: number): boolean;
    function hasIsInvertedMaskBit(flag: number): boolean;
    function hasIsVisibleBit(flag: number): boolean;
    function hasVisibilityDidChangeBit(flag: number): boolean;
    function hasOpacityDidChangeBit(flag: number): boolean;
    function hasRenderOrderDidChangeBit(flag: number): boolean;
  }

  namespace Logging {
    function csmSetLogFunction(logFunction: csmLogFunction): void;
    function csmGetLogFunction(): csmLogFunction | null;
  }

  namespace Version {
    function csmGetVersion(): number;
  }

  type csmLogFunction = (message: string) => void;
}


