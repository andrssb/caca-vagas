// Toda rota /api/* do Pages cai aqui; o resto é arquivo estático de public/.
import { responder, type Env } from "../../src/index";

export const onRequest: PagesFunction<Env> = ({ request, env }) => responder(request, env);
