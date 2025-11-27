/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */

import { Live2DCubismFramework as cubismmodeluserdatajson } from './cubismmodeluserdatajson';
import { Live2DCubismFramework as cubismid } from '../id/cubismid';
import { Live2DCubismFramework as csmstring } from '../type/csmstring';
import { Live2DCubismFramework as csmvector } from '../type/csmvector';
import { Live2DCubismFramework as cubismframework } from '../live2dcubismframework';
// 直接使用命名空间访问，避免类型别名导入时的循环依赖问题
// 辅助函数：安全地获取各种类型和值
function getCubismFramework() {
  if (!cubismframework || !cubismframework.CubismFramework) {
    throw new Error('CubismFramework 未正确加载。请确保 live2dcubismcore.min.js 已加载，并且所有模块依赖已正确解析。');
  }
  return cubismframework.CubismFramework;
}

function getCsmVector() {
  if (!csmvector || !csmvector.csmVector) {
    throw new Error('csmVector 未正确加载。请检查模块依赖。');
  }
  return csmvector.csmVector;
}

function getCsmString() {
  if (!csmstring || !csmstring.csmString) {
    throw new Error('csmString 未正确加载。请检查模块依赖。');
  }
  return csmstring.csmString;
}

function getCubismModelUserDataJson() {
  if (!cubismmodeluserdatajson || !cubismmodeluserdatajson.CubismModelUserDataJson) {
    throw new Error('CubismModelUserDataJson 未正确加载。请检查模块依赖。');
  }
  return cubismmodeluserdatajson.CubismModelUserDataJson;
}

// 类型定义 - 使用命名空间访问类型
type csmVector<T> = typeof csmvector.csmVector extends new (...args: any[]) => infer R ? R : any;
type csmString = typeof csmstring.csmString extends new (...args: any[]) => infer R ? R : any;
type CubismIdHandle = cubismid.CubismIdHandle;
type CubismModelUserDataJson = typeof cubismmodeluserdatajson.CubismModelUserDataJson extends new (...args: any[]) => infer R ? R : any;

export namespace Live2DCubismFramework {
  const ArtMesh = 'ArtMesh';

  /**
   * ユーザーデータインターフェース
   *
   * Jsonから読み込んだユーザーデータを記録しておくための構造体
   */
  export class CubismModelUserDataNode {
    targetType: CubismIdHandle; // ユーザーデータターゲットタイプ
    targetId: CubismIdHandle; // ユーザーデータターゲットのID
    value: csmString; // ユーザーデータ
  }

  /**
   * ユーザデータの管理クラス
   *
   * ユーザデータをロード、管理、検索インターフェイス、解放までを行う。
   */
  export class CubismModelUserData {
    /**
     * インスタンスの作成
     *
     * @param buffer    userdata3.jsonが読み込まれているバッファ
     * @param size      バッファのサイズ
     * @return 作成されたインスタンス
     */
    public static create(
      buffer: ArrayBuffer,
      size: number
    ): CubismModelUserData {
      const ret: CubismModelUserData = new CubismModelUserData();

      ret.parseUserData(buffer, size);

      return ret;
    }

    /**
     * インスタンスを破棄する
     *
     * @param modelUserData 破棄するインスタンス
     */
    public static delete(modelUserData: CubismModelUserData): void {
      if (modelUserData != null) {
        modelUserData.release();
        modelUserData = null;
      }
    }

    /**
     * ArtMeshのユーザーデータのリストの取得
     *
     * @return ユーザーデータリスト
     */
    public getArtMeshUserDatas(): csmVector<CubismModelUserDataNode> {
      return this._artMeshUserDataNode;
    }

    /**
     * userdata3.jsonのパース
     *
     * @param buffer    userdata3.jsonが読み込まれているバッファ
     * @param size      バッファのサイズ
     */
    public parseUserData(buffer: ArrayBuffer, size: number): void {
      let json: CubismModelUserDataJson = new (getCubismModelUserDataJson())(
        buffer,
        size
      );

      const typeOfArtMesh = getCubismFramework().getIdManager().getId(ArtMesh);
      const nodeCount: number = json.getUserDataCount();

      for (let i = 0; i < nodeCount; i++) {
        const addNode: CubismModelUserDataNode = new CubismModelUserDataNode();

        addNode.targetId = json.getUserDataId(i);
        addNode.targetType = getCubismFramework().getIdManager().getId(
          json.getUserDataTargetType(i)
        );
        addNode.value = new (getCsmString())(json.getUserDataValue(i));
        this._userDataNodes.pushBack(addNode);

        if (addNode.targetType == typeOfArtMesh) {
          this._artMeshUserDataNode.pushBack(addNode);
        }
      }

      json.release();
      json = void 0;
    }

    /**
     * コンストラクタ
     */
    public constructor() {
      this._userDataNodes = new (getCsmVector())<CubismModelUserDataNode>();
      this._artMeshUserDataNode = new (getCsmVector())<CubismModelUserDataNode>();
    }

    /**
     * デストラクタ相当の処理
     *
     * ユーザーデータ構造体配列を解放する
     */
    public release(): void {
      for (let i = 0; i < this._userDataNodes.getSize(); ++i) {
        this._userDataNodes.set(i, null);
      }

      this._userDataNodes = null;
    }

    private _userDataNodes: csmVector<CubismModelUserDataNode>; // ユーザーデータ構造体配列
    private _artMeshUserDataNode: csmVector<CubismModelUserDataNode>; // 閲覧リストの保持
  }
}
