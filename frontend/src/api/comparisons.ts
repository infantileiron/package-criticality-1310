import {request} from './client';import type {Comparison} from '../types/domain';
export const list=()=>request<Comparison[]>('/comparisons');
export const create=(data:unknown)=>request<Comparison>('/comparisons',data);
export const rerun=(id:string)=>request<Comparison>('/comparisons/'+id+'/rerun',{});
