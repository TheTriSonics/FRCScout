/*
This is the main repository for data that has to be shared between components
in the application.

Services in Angular can be 'injected' into your components, or other code,
within their constructor.  Only one instance of this object will be created
within the entire appliation and then 'injected' into objects that need
access.  You should never try to manaully create an instance of this class
to access the data insted.  You will not be getting access to the shared
copies.

*/
import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { tap } from 'rxjs/operators';
import { environment } from 'src/environments/environment';
import { ScoutResult } from 'src/app/shared/models/scout-result.model';
import { TBAEvent } from 'src/app/shared/models/tba-event.model';
import { TBATeam } from 'src/app/shared/models/tba-team.model';
import { TBAMatch } from 'src/app/shared/models/tba-match.model';
import { OPRData } from 'src/app/shared/models/opr-data-model';
import { AppSettings } from 'src/app/shared/models/app-settings.model';
import * as _ from 'lodash';
import { PitResult } from '../models/pit-result.model';

@Injectable({
  providedIn: 'root',
})
export class AppDataService {
  /*
  Here we begin declaring some variables that can be used to store our general
  application status.

  We start with the data that we want to keep track of while scouting a
  match. We don't store this data in the actual component that displays and
  handles the button presses for scoring. If we did the application would
  lose state if the user navigated off it and had to come back. Storing it
  here allows us to keep in case that happens.

  We are also able to hook into changes to the data and force them to storage
  in the event that we need to reload the application entirely.
  */

  public scoutingData: ScoutResult = {} as ScoutResult;

  /*
  Here we create a list of drive trains that we will be able to select
  from later.
  */
  public driveTrainList: string[] = [
    'Swerve',
    'Tank',
  ];

  /*
  TODO:
  This is a quick hack to avoid using TBA to load evey event and instead
  we just define ones the TriSonics are involved with.
  */
  get eventList(): TBAEvent[] {
    return _.orderBy(this._eventList, 'eventDate', 'desc');
  }

  private _eventList: TBAEvent[] = [];

  /*
  This is a 'Dictionary' type object that maps an 'eventKey' property of
  the string type to a list of TBATeam objects. The list of teams doesn't
  change often per event so we just cache the data to prevent multiple
  lookups.
  */
  private _eventTeamsCache: { [eventKey: string]: TBATeam[] } = {};

  private _eventMatchesCache: { [eventKey: string]: TBAMatch[] } = {};

  /*
  The _held variable are used to hold data that needs to tbe sent to the API
  for storage but hasn't yet.

  In the case that an event doesn't have data service on the match floor
  users can hold their data in this storage and a portion of the UI is
  dedicated to retying the upload of it.
  */
  private _heldScoutData: ScoutResult[] = [];

  private _heldPitData: PitResult[] = [];

  /*
  We use this to keep the name of the user
  */
  private _scouterName = '';

  /*
  Team Key is a secret key that is used to keep data to the collecting team.
  A bit of rework is needed in how this is handled and it's name through the
  code.
  */
  private _teamKey = '';

  // Okay, going to just name it secret and start fixing this.
  private _secretKey = '';

  private _eventKey = '';

  private _eventName = '';

  private _showConfetti = true;

  // Shorthand to prevent using the full name to the environment setting
  private baseUrl = environment.baseUrl;

  /*
  Now we create a series of getter and setter methods to access the private
  variables we declare above with the _ prefix. This lets the outside code
  work with them as if they were just public members but we can decide if an
  event is worth flushing to storage or not here, not at something in the UI
  layer.
  */
  public get scouterName(): string {
    return this._scouterName;
  }

  public set scouterName(v: string) {
    this._scouterName = v;
    // This is how we store data to storage in case we have to restart
    this.saveSettings();
  }

  public get teamKey(): string {
    return this._teamKey;
  }

  public set teamKey(v: string) {
    this._teamKey = v;
    this.saveSettings();
  }

  public get secretKey(): string {
    return this._secretKey;
  }

  public set secretKey(v: string) {
    this._secretKey = v;
    this.saveSettings();
  }

  public get eventKey(): string {
    return this._eventKey;
  }

  public set eventKey(v: string) {
    this._eventKey = v;
    this._eventName = this._eventList.find((e) => e.key === v)?.short_name ?? '';
    this.saveSettings();
  }

  public get eventName(): string {
    return this._eventName || 'undefined';
  }

  public set showConfetti(v: boolean) {
    this._showConfetti = v;
    this.saveSettings();
  }

  public get showConfetti(): boolean {
    return this._showConfetti;
  }

  constructor(private httpClient: HttpClient) {
    /*
    Only one instance of this object will ever be created, at startup, so
    this is where we load our data from disk as the app starts.
    */
    this.loadSettings();
    this.loadEvents();
  }

  /*
  There are a number of ways for an app to store data within a browser
  long term. We'll be using the simple key/value pair that 'LocalStorage'
  offers. To keep thing simple we'll store the data we're concerned with
  as JSON strings as the value of each key.

  JSON stands for JavaScript Object Notation and is a data transport/storage
  format that is a snippet of valid JavaScript code describes something.
  */
  private saveSettings(): void {
    const d: AppSettings = {
      showConfetti: this.showConfetti,
      scouterName: this.scouterName,
      secretKey: this.secretKey,
      eventKey: this.eventKey,
    };
    /*
    Yes the standard function is called 'stringify'. I didn't do anything
    weird to call it that.
    */
    localStorage.setItem('appSettings', JSON.stringify(d));
    localStorage.setItem(
      '_eventTeamsCache',
      JSON.stringify(this._eventTeamsCache),
    );
    localStorage.setItem('_heldScoutData', JSON.stringify(this._heldScoutData));
    localStorage.setItem('_heldPitData', JSON.stringify(this._heldPitData));
    localStorage.setItem('_eventList', JSON.stringify(this._eventList));
  }

  private loadEvents(): void {
    this.getEvents(2024).subscribe((events) => {
      console.log('events', JSON.stringify(events));
      console.log(events);
      this._eventList = events;
      // Force an update to the name property by doing this assignment
      this.eventKey = this._eventKey
      this.saveSettings();
    });
  }

  /*
  Here we load our JSON strings from LocalStorage for use but if nothing
  is found a default/blank value that the application will function with
  is passed back instead.
  */
  private loadSettings(): void {
    const rawJson = localStorage.getItem('appSettings') ?? '{}';
    const d: AppSettings = JSON.parse(rawJson);
    const teamCacheJson = localStorage.getItem('_eventTeamsCache') ?? '[]';
    this._eventTeamsCache = JSON.parse(teamCacheJson);
    const scoutDataJson = localStorage.getItem('_heldScoutData') ?? '[]';
    this._heldScoutData = JSON.parse(scoutDataJson);
    const pitDataJson = localStorage.getItem('_heldPitData') ?? '[]';
    this._heldPitData = JSON.parse(pitDataJson).splice(0, 1);
    const eventListJson = localStorage.getItem('_eventList') ?? '[]';
    this._eventList = JSON.parse(eventListJson).splice(0, 1);
    this._scouterName = d.scouterName;
    this.eventKey = d.eventKey;
    this._teamKey = d.secretKey;
    this._secretKey = d.secretKey;
  }

  /*
  Here we use the HTTP protocol to collect data from The Blue Aliance
  and cache the results for later use. If the results are already cached
  we use those and save the trouble of the HTTP call.

  The upper layer of the app can use a 'force' option to make it ignore the
  cache.
  */
  public getEventTeamList(
    eventKey: string,
    options?: { force?: boolean },
  ): Observable<TBATeam[]> {
    const force = options?.force ?? false;
    if (
      !force &&
      this._eventTeamsCache[eventKey] &&
      this._eventTeamsCache[eventKey].length > 0
    ) {
      return of(this._eventTeamsCache[eventKey]);
    }
    const url = `${this.baseUrl}/GetTeamsForEvent?event_key=${eventKey}`;
    return this.httpClient.get<TBATeam[]>(url).pipe(
      tap((teams) => {
        this._eventTeamsCache[eventKey] = teams;
        this.saveSettings();
      }),
    );
  }

  public getEventMatchList(
    eventKey: string,
    options?: { force?: boolean },
  ): Observable<TBAMatch[]> {
    const force = options?.force ?? false;
    if (
      !force &&
      this._eventMatchesCache[eventKey] &&
      this._eventMatchesCache[eventKey].length > 0
    ) {
      return of(this._eventMatchesCache[eventKey]);
    }
    const url = `${this.baseUrl}/GetMatchesForEvent?event_key=${eventKey}`;
    return this.httpClient.get<TBAMatch[]>(url).pipe(
      tap((teams) => {
        this._eventMatchesCache[eventKey] = teams;
        this.saveSettings();
      }),
    );
  }

  /* Get all events for a year */
  public getEvents(
    year: number,
  ): Observable<TBAEvent[]> {
    const url = `${this.baseUrl}/GetEvents?year=${year}`;
    return this.httpClient.get<TBAEvent[]>(url).pipe(
      tap((events) => {
        this._eventList = events;
        this.saveSettings();
      }),
    );
  }

  /*
  Inside the API there is a HelloWorld example and this show how we would
  call it from our service.
  */
  public getHelloWorld(): Observable<any> {
    return this.httpClient.get(`${this.baseUrl}/HelloWorld`);
  }

  get heldScoutData(): ScoutResult[] {
    return this._heldScoutData;
  }

  get heldPitData(): PitResult[] {
    return this._heldPitData;
  }


  /*
  Here we store our match scouting results in a local memory cache (array)
  and then the app stores all settings/data again.
  */
  public cacheResults(payload: ScoutResult): void {
    this._heldScoutData.push(payload);
    this.saveSettings();
  }

  /*
  Here we remove a match (or multiple) from our local cache and then the app
  stores all settings/data again.
  */
  public unCacheResults(payload: ScoutResult): void {
    console.log(`Held lengh before ${this._heldScoutData.length}`);
    console.log(payload);
    console.log(this._heldScoutData);
    _.remove(this._heldScoutData, {
      event_key: payload.event_key,
      scouter_name: payload.scouter_name,
      scouting_team: payload.scouting_team,
    });
    _.remove(this._heldScoutData, (i) => Object.keys(i).length === 0);
    console.log(`Held lengh after ${this._heldScoutData.length}`);
    this.saveSettings();
  }

  /*
  We repeat the same pattern here with the pit scouting data and the
  caching mechanism.
  */
  public cachePitResults(payload: PitResult): void {
    this._heldPitData.push(payload);
    this.saveSettings();
  }

  public unCachePitResults(payload: PitResult): void {
    console.log(`Held lengh before ${this._heldPitData.length}`);
    this._heldPitData = _.remove(this._heldPitData, {
      event_key: payload.event_key,
      scouter_name: payload.scouter_name,
      scouting_team: payload.scouting_team,
    });
    console.log(`Held lengh after ${this._heldPitData.length}`);
    this.saveSettings();
  }

  /*
  This method is used by the app to send the results of a scouting match
  to the API for storage in the cloud.
  */
  public postResults(payload: ScoutResult): Observable<ScoutResult> {
    console.log('posting', payload);
    /*
    The uncache and immediately recache was chosen because both methods
    existed and it works. If the event isn't alrady cached the uncache
    has no effect. If multiple entries were in there it removes them all.
    The cache operation is a simple pop onto an array.
    */
    this.unCacheResults(payload);
    this.cacheResults(payload);
    /*
    There's a lot to unpack on this one! We'll keep it high level though.
    We issue an HTTP to our API with this. When it returns our pipe() and
    tap() will trigger the running of the anonymous function we give it with
    an arrow (=>) definition. That function just calls the uncache method.

    The value of r in that function is the return of the HTTP call. We don't
    need to do anything with it here, but we could log it out to the console
    if we wanted.

    The result is also passed along via the Observable that we return from
    the httpClient as a general pattern.
    */
    return this.httpClient.post<ScoutResult>(`${this.baseUrl}/PostResults`, payload).pipe(
      tap((r) => {
        // console.log(r);
        this.unCacheResults(payload);
      }),
    );
  }

  public postPitResults(payload: any): Observable<any> {
    this.unCachePitResults(payload);
    this.cachePitResults(payload);
    return this.httpClient.post(`${this.baseUrl}/PostPitResults`, payload).pipe(
      tap((r) => {
        this.unCachePitResults(payload);
      }),
    );
  }

  public getResults(secretTeamKey: string): Observable<ScoutResult[]> {
    let url = `${this.baseUrl}/GetResults`;
    if (secretTeamKey) {
      url += `?secret_team_key=${secretTeamKey}`;
    }
    return this.httpClient.get<ScoutResult[]>(url);
  }

  public getRobotData(teamKey: number): Observable<ScoutResult[]> {
    let url = `${this.baseUrl}/GetRobotData?secret_team_key=${this._secretKey}`;
    if (teamKey) {
      url += `&team_key=${teamKey}`;
    }
    return this.httpClient.get<ScoutResult[]>(url);
  }

  public getPitResults(
    secretTeamKey: string,
    eventKey: string,
    teamKey: string | null,
  ): Observable<PitResult[]> {
    let url = `${this.baseUrl}/GetPitResults?param=none`;
    if (secretTeamKey) {
      url += `&secret_team_key=${secretTeamKey}`;
    }
    if (eventKey) {
      url += `&event_key=${eventKey}`;
    }
    if (teamKey) {
      url += `&team_key=${teamKey}`;
    }
    return this.httpClient.get<PitResult[]>(url);
  }

  public getOPRData(eventKey: string): Observable<OPRData[]> {
    const url = `${this.baseUrl}/GetOPRData?event_key=${eventKey}`;
    return this.httpClient.get<OPRData[]>(url);
  }
}

export default AppDataService;
