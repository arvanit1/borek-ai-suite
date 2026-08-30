declare module "archiver" {
  import { Transform } from "node:stream";

  export class ZipArchive extends Transform {
    constructor(options?: { zlib?: { level?: number } });
    file(path: string, options: { name: string }): this;
    finalize(): Promise<void>;
  }
}
