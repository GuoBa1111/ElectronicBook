// 服务器配置
export const SERVER_CONFIG = {
  host: '192.168.177.225',
  port: 3000,
  dataPath: 'C:\\Users\\DEH\\Desktop\\电子书项目\\backend\\data',
  get baseUrl() {
    return `http://${this.host}:${this.port}`;
  }
};