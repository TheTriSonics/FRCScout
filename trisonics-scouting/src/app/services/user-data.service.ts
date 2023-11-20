import { Injectable } from '@angular/core';
import { UrlMatchResult } from '@angular/router';
import { ScoutResult } from '../shared/models/scout-result.model';

@Injectable({
  providedIn: 'root'
})
export class UserDataService {

  public scouterName: string = '';

  public eventName: string = '';

  public eventKey: string = '';

  public scoutingData: ScoutResult = {} as ScoutResult;

  constructor() { }
}
